@echo off
title AFS Setup
echo ==============================================
echo       AFS System - First Time Setup
echo ==============================================
echo.

echo 1. Checking Python Installation...
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed or not added to PATH.
    echo Please install Python 3.9+ from python.org and check "Add to PATH".
    pause
    exit /b
)
echo [OK] Python is installed.
echo.

echo 2. Checking Docker Installation...
docker --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [WARNING] Docker not found. Redis will need to be started separately.
    echo Install Docker Desktop from https://docker.com if you want to use docker-compose.
    echo.
) ELSE (
    echo [OK] Docker is installed.
    echo.
)

echo 3. Setting up Virtual Environment (venv)...
IF NOT EXIST "venv\Scripts\activate.bat" (
    python -m venv venv
    echo [OK] Virtual Environment created.
) ELSE (
    echo [OK] Virtual Environment already exists.
)
echo.

echo 4. Activating Virtual Environment...
call venv\Scripts\activate
echo.

echo 5. Installing Python Dependencies...
pip install -r requirements.txt
echo [OK] Dependencies installed.
echo.

echo 6. Installing Playwright Browsers (This may take a few minutes)...
playwright install chromium
echo [OK] Playwright browsers installed.
echo.

echo ==============================================
echo   Setup Complete!
echo.
echo   วิธีรัน (2 วิธี):
echo.
echo   วิธีที่ 1 - Docker (แนะนำ, รองรับหลายคน):
echo     docker-compose up --build
echo.
echo   วิธีที่ 2 - รันแยก (Local development):
echo     1. เปิด Redis: docker run -d -p 6379:6379 redis:7-alpine
echo     2. เปิด Celery: AFS-worker.bat
echo     3. เปิด Flask:  AFS.bat
echo ==============================================
pause
