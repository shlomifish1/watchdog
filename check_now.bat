@echo off
title InnerBalance Watchdog
chcp 65001 >nul 2>&1
set PYTHONIOENCODING=utf-8

set PYTHON=C:\Users\fishman-ai-server\Desktop\ai_agents\.venv\Scripts\python.exe
set SCRIPT=C:\Users\fishman-ai-server\Desktop\watchdog\watchdog.py

echo.
echo ============================================
echo  InnerBalance OS - Service Check
echo ============================================
echo.

"%PYTHON%" "%SCRIPT%"

echo.
echo ============================================
echo  Done.
echo ============================================
echo.
pause
