import json
import os
import redis as redis_lib

from celery_app import celery
from automation import run_automation
from notifier import notify_job_result

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
_redis = redis_lib.from_url(REDIS_URL)


def _publish(channel: str, data: dict):
    """ส่ง log ไปยัง Redis Pub/Sub channel ของ task นั้นๆ"""
    try:
        _redis.publish(channel, json.dumps(data, ensure_ascii=False))
    except Exception as e:
        print(f"[Redis Publish Error] {e}")


@celery.task(bind=True, name="tasks.run_automation_task")
def run_automation_task(self, username, password, temp_min, temp_max,
                        start_row, end_row, time_period, show_browser,
                        u_value, speed, label=None, notif_username=None, is_auto=False):
    """
    Celery task สำหรับรันบอทอัตโนมัติ
    - แต่ละ task มี self.request.id (task_id) เป็น unique identifier
    - Log ถูก publish ไป Redis channel: task:<task_id>
    - หยุดได้โดยดึง flag จาก Redis key: stop:<task_id>
    """
    task_id = self.request.id
    channel = f"task:{task_id}"
    stop_key = f"stop:{task_id}"
    pause_key = f"pause:{task_id}"

    # ล้าง flag เก่า (กรณี task_id ซ้ำ - ไม่น่าเกิดแต่ป้องกันไว้)
    _redis.delete(stop_key, pause_key)

    state = {
        "should_stop": False,
        "paused": False,
        "_task_id": task_id,
        "_redis": _redis,
        "_stop_key": stop_key,
        "_pause_key": pause_key,
    }

    success = False
    last_message = "ไม่ทราบผลลัพธ์"

    if label is None:
        label = f"งาน ({time_period})"

    _publish(channel, {"type": "info", "message": f"[Task {task_id[:8]}] เริ่มต้นทำงาน: {label}"})

    try:
        for log_line in run_automation(
            username, password, temp_min, temp_max,
            start_row, end_row, time_period, show_browser,
            u_value, speed, state
        ):
            # ตรวจสอบ stop flag จาก Redis ทุก iteration
            if _redis.exists(stop_key):
                state["should_stop"] = True

            # ตรวจสอบ pause flag
            state["paused"] = bool(_redis.exists(pause_key))

            try:
                log_data = json.loads(log_line)
                _publish(channel, log_data)
                
                if is_auto and notif_username:
                    _redis.rpush(f"bg_logs:{notif_username}", log_line)
                    _redis.expire(f"bg_logs:{notif_username}", 3600)

                msg_type = log_data.get("type", "info")
                if msg_type == "success":
                    success = True
                    last_message = log_data.get("message", "")
                elif msg_type == "error":
                    last_message = log_data.get("message", "")
            except Exception:
                _publish(channel, {"type": "info", "message": log_line.strip()})

    except Exception as e:
        _publish(channel, {"type": "error", "message": f"เกิดข้อผิดพลาดร้ายแรง: {str(e)}"})
        last_message = str(e)
    finally:
        # ทำความสะอาด Redis keys
        _redis.delete(stop_key, pause_key)

        # ส่งสัญญาณปิด SSE stream
        _publish(channel, {"type": "done", "message": "การทำงานสิ้นสุดแล้ว"})

        # Discord notification
        notify_job_result(label, success, last_message, username=notif_username)

        if is_auto and notif_username:
            final_status = {"type": "success" if success else "error", "message": last_message}
            _redis.rpush(f"bg_logs:{notif_username}", json.dumps(final_status, ensure_ascii=False))
            _redis.expire(f"bg_logs:{notif_username}", 3600)

    return {"success": success, "message": last_message}
