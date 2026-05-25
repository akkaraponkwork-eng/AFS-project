@echo off
echo Starting Auto-Fill Web App...
call venv\Scripts\activate

echo Opening web browser...
start http://127.0.0.1:5000

python app.py
pause
