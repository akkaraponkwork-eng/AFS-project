@echo off
title AFS Web Server
echo ==============================================
echo       AFS Web Server (Flask)
echo ==============================================
echo.
echo [INFO] ตรวจสอบว่า Redis และ Celery Worker กำลังรันอยู่!
echo.
call venv\Scripts\activate
set REDIS_URL=redis://localhost:6379/0

echo Opening web browser...
start http://127.0.0.1:5000

python app.py
pause
