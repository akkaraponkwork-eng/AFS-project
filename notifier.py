import os
import json
import urllib.request
from datetime import datetime

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

def send_discord_notification(title, description, color, fields):
    if not DISCORD_WEBHOOK_URL:
        return False

    payload = {
        "embeds": [
            {
                "title": title,
                "description": description,
                "color": color,
                "fields": fields,
                "footer": {
                    "text": "AFS Automation Bot"
                }
            }
        ]
    }
    
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'AFS-Bot/1.0'
    }
    
    try:
        req = urllib.request.Request(
            DISCORD_WEBHOOK_URL, 
            data=json.dumps(payload).encode('utf-8'), 
            headers=headers, 
            method='POST'
        )
        with urllib.request.urlopen(req) as response:
            if response.status in (200, 204):
                return True
    except Exception as e:
        print(f"[Notifier Error] {e}")
    return False

def notify_startup(url):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fields = [
        {"name": "🔗 Public URL", "value": f"[คลิกเพื่อเปิดระบบที่นี่]({url})", "inline": False},
        {"name": "⏱️ Started At", "value": current_time, "inline": True}
    ]
    return send_discord_notification("🚀 AFS System Started!", "บอทสำหรับกรอกข้อมูลอุณหภูมิอัตโนมัติพร้อมใช้งานแล้ว", 6516977, fields)

def notify_job_result(label, success, message):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    title = f"✅ ทำงานเสร็จสิ้น ({label})" if success else f"❌ เกิดข้อผิดพลาด ({label})"
    color = 1082400 if success else 15548997  # Green or Red
    
    fields = [
        {"name": "รายละเอียด", "value": message, "inline": False},
        {"name": "เวลา", "value": current_time, "inline": True}
    ]
    return send_discord_notification(title, "รายงานการทำงานอัตโนมัติ (Background)", color, fields)
