@echo off
set PYTHONIOENCODING=utf-8
chcp 65001 >nul 2>&1
set PYTHON=C:\Users\fishman-ai-server\Desktop\ai_agents\.venv\Scripts\pythonw.exe
set SCRIPT=C:\Users\fishman-ai-server\Desktop\watchdog\watchdog.py
set DASHBOARD_URL=http://127.0.0.1:8000/status
if not exist "%PYTHON%" set PYTHON=C:\Users\fishman-ai-server\Desktop\ai_agents\.venv\Scripts\python.exe
start "" "%PYTHON%" "%SCRIPT%" --bootstrap-core --loop --interval 1 --quiet --auto-restart
start "" /b powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 7; Start-Process '%DASHBOARD_URL%'"
exit /b 0
