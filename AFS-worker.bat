@echo off
title AFS Celery Worker
echo ==============================================
echo       AFS Celery Worker (Multi-User Queue)
echo ==============================================
echo.
echo [INFO] ตรวจสอบให้แน่ใจว่า Redis กำลังรันอยู่ก่อน!
echo [INFO] รัน Redis: docker run -d -p 6379:6379 redis:7-alpine
echo.

call venv\Scripts\activate
set REDIS_URL=redis://localhost:6379/0

echo [START] กำลังเริ่ม Celery Worker (pool=threads, concurrency=10)...
celery -A celery_app worker --pool=threads --concurrency=10 --loglevel=info
pause
