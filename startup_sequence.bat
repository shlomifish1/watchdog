@echo off
chcp 65001 >nul 2>&1
cd /d "C:\Users\fishman-ai-server\Desktop\watchdog"

echo =====================================================
echo   InnerBalance OS - Startup Sequence
echo =====================================================
echo.
echo Waiting 30 seconds for system to fully load...
timeout /t 30 /nobreak >nul

echo.
echo [1/2] Restarting all services (restart_all.py)...
"C:\Users\fishman-ai-server\AppData\Local\Programs\Python\Python312\python.exe" restart_all.py

echo.
echo [2/2] Launching watchdog monitor (background)...
start "" /b "C:\Users\fishman-ai-server\AppData\Local\Programs\Python\Python312\pythonw.exe" "C:\Users\fishman-ai-server\Desktop\watchdog\watchdog.py"

echo.
echo Startup sequence complete.
exit /b 0
