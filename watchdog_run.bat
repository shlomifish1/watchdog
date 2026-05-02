@echo off
setlocal EnableExtensions EnableDelayedExpansion
set PYTHONIOENCODING=utf-8
chcp 65001 >nul 2>&1
cd /d "%~dp0"
set PYTHON=python
set SCRIPT=%~dp0watchdog.py
set LOCKFILE=%~dp0locks\watchdog.lock

:: Prevent duplicate watchdog instances via lock file
if exist "%LOCKFILE%" (
    set /p EXISTING_PID=<"%LOCKFILE%"
    if not defined EXISTING_PID (
        echo Lock file exists but PID is empty. Continuing startup.
    ) else (
        powershell -NoProfile -Command "if (Get-Process -Id !EXISTING_PID! -ErrorAction SilentlyContinue) { exit 1 } else { exit 0 }"
    )
    if errorlevel 1 (
        echo Watchdog already running with PID=!EXISTING_PID!, exiting.
        echo.
        pause
        exit /b 0
    )
)

echo Starting watchdog...
echo Python: %PYTHON%
echo Script: %SCRIPT%
echo.
"%PYTHON%" "%SCRIPT%"
set EXIT_CODE=%ERRORLEVEL%
echo.
echo Watchdog exited with code %EXIT_CODE%.
pause
exit /b %EXIT_CODE%
