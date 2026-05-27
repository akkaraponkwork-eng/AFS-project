from flask import Flask, render_template, request, jsonify, Response, session, redirect, url_for
from automation import run_automation
import json
import secrets
from datetime import timedelta, datetime
import threading
import time
import os
from notifier import notify_job_result

import queue
from collections import deque

app = Flask(__name__)
app.secret_key = "rtamed_automation_bot_secret_key"
app.permanent_session_lifetime = timedelta(days=30)

# In-memory background log buffer (max 500 entries)
bg_log_buffer = deque(maxlen=500)
bg_log_counter = 0
bg_log_lock = threading.Lock()

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
PRESETS_FILE = os.path.join(DATA_DIR, "presets.json")
ACTIVE_STATE_FILE = os.path.join(DATA_DIR, "active_state.json")

def get_default_presets():
    return {
        "active_preset": "Default",
        "presets": {
            "Default": {
                "showBrowser": False,
                "typingSpeed": "normal",
                "tabs": []
            }
        }
    }

def load_presets():
    if not os.path.exists(PRESETS_FILE):
        return {"presets": {}}
    try:
        with open(PRESETS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {"presets": {}}

def save_presets(data):
    with open(PRESETS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_active_state():
    if not os.path.exists(ACTIVE_STATE_FILE):
        return {}
    try:
        with open(ACTIVE_STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_active_state(data):
    with open(ACTIVE_STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', username=session['username'])

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username and password:
            session.permanent = True
            session['username'] = username
            session['password'] = password
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error="กรุณากรอก Username และ Password")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/service-worker.js')
def service_worker():
    return app.send_static_file('service-worker.js')

@app.route('/api/bg_logs')
def bg_logs_api():
    since = int(request.args.get('since', 0))
    with bg_log_lock:
        all_logs = list(bg_log_buffer)
    # all_logs is list of (index, log_data)
    new_logs = [entry for entry in all_logs if entry[0] >= since]
    next_index = new_logs[-1][0] + 1 if new_logs else since
    return jsonify({
        'logs': [entry[1] for entry in new_logs],
        'next_index': next_index
    })

automation_state = {"should_stop": False, "paused": False}

@app.route('/api/stop', methods=['POST'])
def stop_automation():
    automation_state["should_stop"] = True
    return jsonify({"success": True, "message": "ส่งคำสั่งยกเลิกแล้ว"})

@app.route('/api/pause', methods=['POST'])
def pause_automation():
    automation_state["paused"] = True
    return jsonify({"success": True, "message": "ส่งคำสั่งหยุดชั่วคราวแล้ว"})

@app.route('/api/resume', methods=['POST'])
def resume_automation():
    automation_state["paused"] = False
    return jsonify({"success": True, "message": "ส่งคำสั่งทำงานต่อแล้ว"})

@app.route('/api/presets', methods=['GET'])
def get_presets_api():
    if 'username' not in session:
        return jsonify({"success": False, "message": "ไม่ได้เข้าสู่ระบบ"}), 401
    return jsonify(load_presets())

@app.route('/api/presets', methods=['POST'])
def save_preset_api():
    if 'username' not in session:
        return jsonify({"success": False, "message": "ไม่ได้เข้าสู่ระบบ"}), 401
    
    req = request.json
    preset_name = req.get("preset_name", "Default")
    preset_data = req.get("preset_data", {})
    
    data = load_presets()
    if "presets" not in data:
        data["presets"] = {}
        
    data["presets"][preset_name] = preset_data
    save_presets(data)
    
    return jsonify({"success": True, "message": f"บันทึกโปรไฟล์ '{preset_name}' เรียบร้อยแล้ว"})

@app.route('/api/presets/<preset_name>', methods=['DELETE'])
def delete_preset_api(preset_name):
    if 'username' not in session:
        return jsonify({"success": False, "message": "ไม่ได้เข้าสู่ระบบ"}), 401
        
    data = load_presets()
    if preset_name in data.get("presets", {}):
        if preset_name == "Default":
            return jsonify({"success": False, "message": "ไม่สามารถลบโปรไฟล์ Default ได้"}), 400
            
        del data["presets"][preset_name]
        
        # If active preset was deleted, fallback to Default
        if data.get("active_preset") == preset_name:
            data["active_preset"] = "Default"
            
        save_presets(data)
        return jsonify({"success": True, "message": f"ลบโปรไฟล์ '{preset_name}' แล้ว"})
    
    return jsonify({"success": False, "message": "ไม่พบโปรไฟล์ที่ระบุ"}), 404

@app.route('/api/active_state', methods=['GET'])
def get_active_state_api():
    if 'username' not in session:
        return jsonify({"success": False, "message": "ไม่ได้เข้าสู่ระบบ"}), 401
    return jsonify(load_active_state())

@app.route('/api/active_state', methods=['POST'])
def save_active_state_api():
    if 'username' not in session:
        return jsonify({"success": False, "message": "ไม่ได้เข้าสู่ระบบ"}), 401
        
    state_data = request.json
    
    # Preserve last_run flags only if the scheduleTime hasn't changed
    existing_state = load_active_state()
    if "tabs" in existing_state and "tabs" in state_data:
        for idx, new_tab in enumerate(state_data["tabs"]):
            if idx < len(existing_state["tabs"]):
                old_tab = existing_state["tabs"][idx]
                # If schedule time is the same, preserve the last_run flag
                if old_tab.get("scheduleTime") == new_tab.get("scheduleTime"):
                    last_run_key = f"last_run_{idx}"
                    if last_run_key in existing_state:
                        state_data[last_run_key] = existing_state[last_run_key]
            
    state_data["credentials"] = {
        "username": session.get('username'),
        "password": session.get('password')
    }
    save_active_state(state_data)
    return jsonify({"success": True, "message": "บันทึกการตั้งค่าสำหรับรันเบื้องหลังเรียบร้อยแล้ว"})

@app.route('/api/schedule_status')
def schedule_status():
    """Debug endpoint: shows current active schedule and server time."""
    active_config = load_active_state()
    now = datetime.now()
    tabs_info = []
    if active_config and "tabs" in active_config:
        for idx, tab in enumerate(active_config["tabs"]):
            tabs_info.append({
                "tab": idx + 1,
                "enabled": tab.get("enabled"),
                "scheduleTime": tab.get("scheduleTime"),
                "timePeriod": tab.get("timePeriod"),
                "last_run": active_config.get(f"last_run_{idx}", "never"),
            })
    return jsonify({
        "server_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "current_HH:MM": now.strftime("%H:%M"),
        "has_credentials": bool(active_config.get("credentials", {}).get("username")),
        "tabs": tabs_info
    })

@app.route('/api/start', methods=['GET'])
def start_automation():
    username = session.get('username')
    password = session.get('password')
    temp_min = float(request.args.get('tempMin', 35.9))
    temp_max = float(request.args.get('tempMax', 36.1))
    start_row = int(request.args.get('startRow', 1))
    end_row = int(request.args.get('endRow', 39))
    time_period = request.args.get('timePeriod', 'morning')
    show_browser = request.args.get('showBrowser', 'true') == 'true'
    u_value = request.args.get('uValue', 'skip')
    speed = request.args.get('speed', 'normal')

    if not username or not password:
        return jsonify({"success": False, "message": "ไม่ได้เข้าสู่ระบบ หรือเซสชั่นหมดอายุ"}), 401

    automation_state["should_stop"] = False
    automation_state["paused"] = False

    def generate():
        for log_line in run_automation(username, password, temp_min, temp_max, start_row, end_row, time_period, show_browser, u_value, speed, automation_state):
            yield f"data: {log_line}\n\n"

    return Response(generate(), mimetype='text/event-stream')


# --- Backend Scheduler ---
task_queue = queue.Queue()

def background_worker():
    while True:
        task_data = task_queue.get()
        if task_data is None:
            break
        try:
            execute_background_task(*task_data)
        except Exception as e:
            print(f"[Worker Error] {e}")
        finally:
            task_queue.task_done()

# Start a single worker thread to process background tasks sequentially
worker_thread = threading.Thread(target=background_worker, daemon=True)
worker_thread.start()

def push_bg_log(message, log_type='info', **kwargs):
    global bg_log_counter
    with bg_log_lock:
        entry = {'type': log_type, 'message': message}
        entry.update(kwargs)
        bg_log_buffer.append((bg_log_counter, entry))
        bg_log_counter += 1

def execute_background_task(username, password, task, show_browser, speed, idx):
    try:
        temp_min = float(task.get("tempMin", 35.9))
        temp_max = float(task.get("tempMax", 36.1))
        start_row = int(task.get("startRow", 1))
        end_row = int(task.get("endRow", 39))
        time_period = task.get("timePeriod", "morning")
        u_value = task.get("uValue", "skip")
        label = f"ช่วงที่ {idx+1} ({time_period})"
        
        push_bg_log(f"[Auto] เริ่มทำงาน: {label} (rows {start_row}-{end_row})", 'info', bg_task_start=True)
        
        state = {"should_stop": False, "paused": False}
        success = False
        message = "Unknown result"
        
        for log_line in run_automation(username, password, temp_min, temp_max, start_row, end_row, time_period, show_browser, u_value, speed, state):
            try:
                log_data = json.loads(log_line)
                msg = log_data.get("message", "")
                log_type = log_data.get("type", "info")
                if msg:
                    push_bg_log(msg, log_type)
                if log_type == "success":
                    success = True
                    message = msg
                elif log_type == "error":
                    message = msg
            except:
                pass
                
        notify_job_result(label, success, message)
    except Exception as e:
        push_bg_log(f"[Auto Error] {str(e)}", 'error')
        notify_job_result(f"ช่วงที่ {idx+1}", False, str(e))

def background_scheduler():
    print("[Scheduler] Started — checking every minute")
    while True:
        try:
            now = datetime.now()
            current_time_str = now.strftime("%H:%M")
            
            schedules = load_active_state()
            if schedules and "tabs" in schedules:
                credentials = schedules.get("credentials", {})
                username = credentials.get("username")
                password = credentials.get("password")
                
                if username and password:
                    for idx, tab in enumerate(schedules["tabs"]):
                        sched_time = (tab.get("scheduleTime") or "").strip()
                        if tab.get("enabled") and sched_time == current_time_str:
                            last_run_key = f"last_run_{idx}"
                            today_str = now.strftime("%Y-%m-%d")
                            if schedules.get(last_run_key) != today_str:
                                # Update last run flag for this specific tab
                                schedules[last_run_key] = today_str
                                save_active_state(schedules)
                                
                                print(f"[Scheduler] Queuing task Tab {idx+1} at {current_time_str}")
                                push_bg_log(f"[Scheduler] เริ่มคิวงานอัตโนมัติ Tab {idx+1} เวลา {current_time_str}", 'info', bg_task_start=True)
                                task_queue.put((
                                    username, password, tab,
                                    schedules.get("showBrowser", False),
                                    schedules.get("typingSpeed", "normal"),
                                    idx
                                ))
        except Exception as e:
            print(f"[Scheduler Error] {e}")
        
        # Sleep precisely until the start of the next minute
        now = datetime.now()
        sleep_secs = 60 - now.second - now.microsecond / 1_000_000
        time.sleep(sleep_secs)

# Start scheduler thread
scheduler_thread = threading.Thread(target=background_scheduler, daemon=True)
scheduler_thread.start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5000)
