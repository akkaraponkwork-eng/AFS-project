from flask import (
    Flask, render_template, request, jsonify,
    Response, session, redirect, url_for
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import json
import os
import time
import redis as redis_lib
from datetime import timedelta, datetime
from collections import deque
import threading

from models import db, UserPreset, UserSchedule, ScheduleLastRun, UserCredential
from notifier import notify_job_result, notify_startup
from celery_app import celery

# ─── App Setup ───────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "rtamed_afs_multiuser_2024_secret")
app.permanent_session_lifetime = timedelta(days=30)

# SQLite database เก็บใน data/ (ใช้ absolute path เพื่อความแน่นอน)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "afs.db")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

# ─── Redis ────────────────────────────────────────────────────────────────────
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
_redis = redis_lib.from_url(REDIS_URL, decode_responses=True)

# ─── Flask-Login ──────────────────────────────────────────────────────────────
login_manager = LoginManager(app)
login_manager.login_view = "login"

class SessionUser(UserMixin):
    """Lightweight user object backed by Flask session (ไม่ต้องมีตารางผู้ใช้)"""
    def __init__(self, username):
        self.id = username
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    if "username" in session and session["username"] == user_id:
        return SessionUser(user_id)
    return None

# ─── Flask-Limiter ────────────────────────────────────────────────────────────
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per minute"],
    storage_uri=REDIS_URL,
)

# ─── DB Init ──────────────────────────────────────────────────────────────────
with app.app_context():
    db.create_all()


# ─── Routes: Auth ─────────────────────────────────────────────────────────────
@app.route("/")
@login_required
def index():
    return render_template("index.html", username=current_user.username)

@app.route("/login", methods=["GET", "POST"])
@limiter.limit("20 per minute")
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "").strip()

        # ── Access Control: username ต้องขึ้นต้นด้วย "an" ──
        if not username.lower().startswith("an"):
            return render_template(
                "login.html",
                error="ไม่มีสิทธิ์เข้าใช้งาน: ชื่อผู้ใช้ต้องขึ้นต้นด้วย 'an'"
            )

        if not username or not password:
            return render_template("login.html", error="กรุณากรอก Username และ Password")

        user = SessionUser(username)
        login_user(user, remember=True)
        session.permanent = True
        session["username"] = username
        session["password"] = password

        # บันทึกรหัสผ่านสำหรับบอทแบบถาวร
        cred = UserCredential.query.filter_by(username=username).first()
        if cred:
            cred.bot_password = password
        else:
            cred = UserCredential(username=username, bot_password=password)
            db.session.add(cred)
        db.session.commit()
        
        return redirect(url_for("index"))

    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for("login"))

@app.route("/service-worker.js")
def service_worker():
    return app.send_static_file("service-worker.js")


# ─── Routes: Automation Control ───────────────────────────────────────────────
@app.route("/api/start", methods=["POST"])
@login_required
@limiter.limit("10 per minute")
def start_automation():
    """ส่งงานไป Celery Queue → คืน task_id กลับมา"""
    from tasks import run_automation_task

    username = current_user.username
    password = session.get("password")

    # ถ้าไม่มีใน session (เช่น ปิดเบราว์เซอร์แล้วกลับมาใหม่ด้วย Remember Me) ให้ดึงจากฐานข้อมูลถาวร
    if not password:
        from models import UserCredential
        cred = UserCredential.query.filter_by(username=username).first()
        if cred:
            password = cred.bot_password

    if not password:
        return jsonify({"success": False, "message": "กรุณาล็อกอินใหม่เพื่อต่ออายุรหัสผ่านบอท"}), 401

    data = request.json or {}
    temp_min    = float(data.get("tempMin", 35.9))
    temp_max    = float(data.get("tempMax", 36.1))
    start_row   = int(data.get("startRow", 1))
    end_row     = int(data.get("endRow", 39))
    time_period = data.get("timePeriod", "morning")
    show_browser= bool(data.get("showBrowser", False))
    u_value     = data.get("uValue", "skip")
    speed       = data.get("speed", "normal")
    label       = data.get("label", f"ช่วง ({time_period})")

    task = run_automation_task.apply_async(args=[
        username, password, temp_min, temp_max,
        start_row, end_row, time_period, show_browser,
        u_value, speed, label, username
    ])

    return jsonify({"success": True, "task_id": task.id})


@app.route("/api/stream/<task_id>")
@login_required
def stream_task(task_id):
    """SSE endpoint — subscribe Redis Pub/Sub channel ของ task นั้นๆ"""
    def generate():
        pubsub = _redis.pubsub()
        channel = f"task:{task_id}"
        pubsub.subscribe(channel)

        try:
            # ส่ง heartbeat ทุก 15 วินาที เพื่อป้องกัน connection timeout
            last_heartbeat = time.time()

            for message in pubsub.listen():
                if message["type"] == "message":
                    data = message["data"]
                    yield f"data: {data}\n\n"

                    # ถ้า task ส่ง done signal → ปิด stream
                    try:
                        parsed = json.loads(data)
                        if parsed.get("type") == "done":
                            break
                    except Exception:
                        pass

                # Heartbeat
                now = time.time()
                if now - last_heartbeat > 15:
                    yield ": heartbeat\n\n"
                    last_heartbeat = now

        except GeneratorExit:
            pass
        finally:
            pubsub.unsubscribe(channel)
            pubsub.close()

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/stop/<task_id>", methods=["POST"])
@login_required
def stop_task(task_id):
    """ตั้ง Redis flag ให้ automation loop หยุด + revoke Celery task"""
    _redis.set(f"stop:{task_id}", "1", ex=3600)
    celery.control.revoke(task_id, terminate=True)
    return jsonify({"success": True, "message": "ส่งคำสั่งยกเลิกแล้ว"})


@app.route("/api/pause/<task_id>", methods=["POST"])
@login_required
def pause_task(task_id):
    _redis.set(f"pause:{task_id}", "1", ex=3600)
    return jsonify({"success": True, "message": "ส่งคำสั่งหยุดชั่วคราวแล้ว"})


@app.route("/api/resume/<task_id>", methods=["POST"])
@login_required
def resume_task(task_id):
    _redis.delete(f"pause:{task_id}")
    return jsonify({"success": True, "message": "ส่งคำสั่งทำงานต่อแล้ว"})


# ─── Routes: Presets (แยกตาม user) ────────────────────────────────────────────
@app.route("/api/presets", methods=["GET"])
@login_required
def get_presets():
    username = current_user.username
    presets = UserPreset.query.filter_by(username=username).all()
    result = {p.name: json.loads(p.data_json) for p in presets}
    return jsonify({"presets": result})


@app.route("/api/presets", methods=["POST"])
@login_required
def save_preset():
    username = current_user.username
    req = request.json or {}
    name = req.get("preset_name", "Default")
    data = req.get("preset_data", {})

    preset = UserPreset.query.filter_by(username=username, name=name).first()
    if preset:
        preset.data_json = json.dumps(data, ensure_ascii=False)
    else:
        preset = UserPreset(username=username, name=name, data_json=json.dumps(data, ensure_ascii=False))
        db.session.add(preset)

    db.session.commit()
    return jsonify({"success": True, "message": f"บันทึกโปรไฟล์ '{name}' เรียบร้อยแล้ว"})


@app.route("/api/presets/<preset_name>", methods=["DELETE"])
@login_required
def delete_preset(preset_name):
    username = current_user.username
    if preset_name == "Default":
        return jsonify({"success": False, "message": "ไม่สามารถลบโปรไฟล์ Default ได้"}), 400

    preset = UserPreset.query.filter_by(username=username, name=preset_name).first()
    if not preset:
        return jsonify({"success": False, "message": "ไม่พบโปรไฟล์ที่ระบุ"}), 404

    db.session.delete(preset)
    db.session.commit()
    return jsonify({"success": True, "message": f"ลบโปรไฟล์ '{preset_name}' แล้ว"})


# ─── Routes: Active State / Schedule (แยกตาม user) ───────────────────────────
@app.route("/api/active_state", methods=["GET"])
@login_required
def get_active_state():
    username = current_user.username
    sched = UserSchedule.query.filter_by(username=username).first()
    if not sched:
        return jsonify({})

    result = {
        "showBrowser": sched.show_browser,
        "typingSpeed": sched.typing_speed,
        "tabs": json.loads(sched.tabs_json),
    }

    # last_run per tab
    last_runs = ScheduleLastRun.query.filter_by(username=username).all()
    for lr in last_runs:
        result[f"last_run_{lr.tab_index}"] = lr.last_run_date

    return jsonify(result)


@app.route("/api/active_state", methods=["POST"])
@login_required
def save_active_state():
    username = current_user.username
    data = request.json or {}

    # Preserve last_run flags (schedule time unchanged)
    sched = UserSchedule.query.filter_by(username=username).first()
    old_tabs = json.loads(sched.tabs_json) if sched else []
    new_tabs = data.get("tabs", [])

    if not sched:
        sched = UserSchedule(username=username)
        db.session.add(sched)

    sched.show_browser = bool(data.get("showBrowser", False))
    sched.typing_speed = data.get("typingSpeed", "normal")
    sched.tabs_json = json.dumps(new_tabs, ensure_ascii=False)
    db.session.commit()

    # ลง password ไว้ใน session เผื่อ scheduler ต้องการ
    # (password ไม่เก็บใน DB เพื่อความปลอดภัย)

    return jsonify({"success": True, "message": "บันทึกการตั้งค่าสำหรับรันเบื้องหลังเรียบร้อยแล้ว"})


# ─── Routes: Background Logs (ใช้ Redis per-user channel แทน deque) ───────────
@app.route("/api/bg_logs")
@login_required
def bg_logs_api():
    """ดึง log สะสมของ user คนนี้จาก Redis List"""
    username = current_user.username
    since = int(request.args.get("since", 0))
    key = f"bg_logs:{username}"

    all_logs = _redis.lrange(key, 0, -1)
    result = []
    for i, raw in enumerate(all_logs):
        if i >= since:
            try:
                result.append(json.loads(raw))
            except Exception:
                result.append({"type": "info", "message": raw})

    next_index = since + len(result)
    return jsonify({"logs": result, "next_index": next_index})


# ─── Routes: Schedule Status (Debug) ─────────────────────────────────────────
@app.route("/api/schedule_status")
@login_required
def schedule_status():
    username = current_user.username
    now = datetime.now()
    sched = UserSchedule.query.filter_by(username=username).first()
    tabs = json.loads(sched.tabs_json) if sched else []
    last_runs = {lr.tab_index: lr.last_run_date
                 for lr in ScheduleLastRun.query.filter_by(username=username).all()}

    tabs_info = [
        {
            "tab": idx + 1,
            "enabled": tab.get("enabled"),
            "scheduleTime": tab.get("scheduleTime"),
            "timePeriod": tab.get("timePeriod"),
            "last_run": last_runs.get(idx, "never"),
        }
        for idx, tab in enumerate(tabs)
    ]

    return jsonify({
        "username": username,
        "server_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "current_HH:MM": now.strftime("%H:%M"),
        "tabs": tabs_info,
    })


# ─── Background Scheduler (APScheduler) ──────────────────────────────────────
def _run_bg_scheduler():
    """Scheduler loop แยกตาม user — queue Celery task เมื่อถึงเวลา"""
    from tasks import run_automation_task
    print("[Scheduler] Started — checking every minute", flush=True)
    with open("/app/scheduler_alive.log", "a") as f:
        f.write("[Scheduler] Thread started successfully\n")
    while True:
        try:
            now = datetime.now()
            current_time_str = now.strftime("%H:%M")
            today_str = now.strftime("%Y-%m-%d")

            # ป้องกัน Gunicorn 4 workers ยิงคำสั่งซ้ำซ้อนในนาทีเดียวกัน (Redis Lock)
            lock_key = f"scheduler_lock_{today_str}_{current_time_str}"
            if not _redis.set(lock_key, "1", nx=True, ex=50):
                # ถ้ามี Worker อื่นได้ lock และจัดการของนาทีนี้ไปแล้ว ให้ข้ามไปนอนรอนาทีถัดไปเลย
                now2 = datetime.now()
                import time
                time.sleep(max(0, 60 - now2.second - now2.microsecond / 1_000_000))
                continue

            with app.app_context():
                with open("scheduler_debug.log", "a") as f:
                    f.write(f"[{current_time_str}] Checking schedules...\n")
                    all_scheds = UserSchedule.query.all()
                    for sched in all_scheds:
                        username = sched.username
                        tabs = json.loads(sched.tabs_json)

                        cred = UserCredential.query.filter_by(username=username).first()
                        password = cred.bot_password if cred else None
                        f.write(f"[{current_time_str}] user={username}, has_password={bool(password)}\n")
                        if not password:
                            continue

                        for idx, tab in enumerate(tabs):
                            sched_time = (tab.get("scheduleTime") or "").strip()
                            f.write(f"[{current_time_str}] tab={idx}, enabled={tab.get('enabled')}, sched_time='{sched_time}'\n")
                            if not (tab.get("enabled") and sched_time == current_time_str):
                                continue

                            run_marker = f"{today_str} {current_time_str}"
                            lr = ScheduleLastRun.query.filter_by(username=username, tab_index=idx).first()
                            f.write(f"[{current_time_str}] run_marker={run_marker}, lr_date={lr.last_run_date if lr else 'None'}\n")
                            if lr and lr.last_run_date == run_marker:
                                continue  # รันไปแล้วสำหรับเวลานี้

                            # บันทึก last_run
                            if not lr:
                                lr = ScheduleLastRun(username=username, tab_index=idx)
                                db.session.add(lr)
                            lr.last_run_date = run_marker
                            db.session.commit()
                            f.write(f"[{current_time_str}] SAVED last_run_date = {run_marker}\n")

                            label = f"ช่วงที่ {idx+1} ({tab.get('timePeriod', '')})"
                            print(f"[Scheduler] Queuing: {username} / Tab {idx+1} at {current_time_str}")

                            # Push log แจ้ง user ใน background log
                            log_key = f"bg_logs:{username}"
                            _redis.rpush(log_key, json.dumps({
                                "type": "info",
                                "message": f"[Scheduler] เริ่มคิวงาน {label} เวลา {current_time_str}",
                                "bg_task_start": True
                            }, ensure_ascii=False))
                            _redis.expire(log_key, 86400)

                            run_automation_task.apply_async(args=[
                                username, password,
                                float(tab.get("tempMin", 35.9)),
                                float(tab.get("tempMax", 36.1)),
                                int(tab.get("startRow", 1)),
                                int(tab.get("endRow", 39)),
                                tab.get("timePeriod", "morning"),
                                sched.show_browser,
                                tab.get("uValue", "skip"),
                                sched.typing_speed,
                                label, username
                            ], kwargs={"is_auto": True})

                # เคลียร์ Cache ของ session สำหรับ thread นี้ เพื่อให้อ่านข้อมูลล่าสุดในรอบถัดไป
                db.session.remove()

        except Exception as e:
            print(f"[Scheduler Error] {e}")

        # นอนจนถึงต้นนาทีถัดไป
        now = datetime.now()
        import time
        time.sleep(max(0, 60 - now.second - now.microsecond / 1_000_000))


# Save password to Redis when user saves active_state (for scheduler use)
@app.route("/api/save_session_password", methods=["POST"])
@login_required
def save_session_password():
    """เก็บ password ใน Redis (TTL 25 ชั่วโมง) เพื่อให้ scheduler ใช้ได้"""
    password = session.get("password")
    if password:
        key = f"session_password:{current_user.username}"
        _redis.setex(key, 25 * 3600, password)
    return jsonify({"success": True})


import sys
print(f"DEBUG APP STARTUP: sys.argv = {sys.argv}", flush=True)
with open("/app/app_imported.log", "w") as f:
    f.write(f"app.py was imported! sys.argv={sys.argv}\n")

if "celery" not in sys.argv[0]:
    scheduler_thread = threading.Thread(target=_run_bg_scheduler, daemon=True)
    scheduler_thread.start()
else:
    print("DEBUG APP STARTUP: Skipping scheduler because 'celery' is in sys.argv[0]", flush=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, port=5000)
