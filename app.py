from flask import Flask, render_template, request, jsonify, Response, session, redirect, url_for
from automation import run_automation
import json
import secrets
from datetime import timedelta

app = Flask(__name__)
# ใช้คีย์คงที่เพื่อให้ Session ไม่หลุดเมื่อปิด/เปิดเซิร์ฟเวอร์ใหม่
app.secret_key = "rtamed_automation_bot_secret_key"
app.permanent_session_lifetime = timedelta(days=30)

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
            session.permanent = True  # ให้เบราว์เซอร์จำค่าไว้ตามที่ตั้งไว้ (30 วัน)
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

    # Reset state
    automation_state["should_stop"] = False
    automation_state["paused"] = False

    def generate():
        for log_line in run_automation(username, password, temp_min, temp_max, start_row, end_row, time_period, show_browser, u_value, speed, automation_state):
            yield f"data: {log_line}\n\n"

    return Response(generate(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
