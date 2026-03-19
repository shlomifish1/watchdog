@echo off
title InnerBalance - Setup Scheduler
chcp 65001 >nul 2>&1

set BAT=C:\Users\fishman-ai-server\Desktop\watchdog\watchdog_run.bat

echo.
echo ============================================
echo  Setting up Watchdog - twice daily
echo  09:00 and 21:00 every day
echo ============================================
echo.

schtasks /delete /tn "InnerBalance_Watchdog_09" /f >nul 2>&1
schtasks /delete /tn "InnerBalance_Watchdog_21" /f >nul 2>&1

echo [1/2] Creating task at 09:00...
schtasks /create /tn "InnerBalance_Watchdog_09" /tr "%BAT%" /sc daily /st 09:00 /ru "%USERNAME%" /rl highest /f
if %errorlevel%==0 (
    echo       OK - InnerBalance_Watchdog_09
) else (
    echo       ERROR creating 09:00 task
)

echo.
echo [2/2] Creating task at 21:00...
schtasks /create /tn "InnerBalance_Watchdog_21" /tr "%BAT%" /sc daily /st 21:00 /ru "%USERNAME%" /rl highest /f
if %errorlevel%==0 (
    echo       OK - InnerBalance_Watchdog_21
) else (
    echo       ERROR creating 21:00 task
)

echo.
echo ============================================
echo  Done! Tasks created:
echo    InnerBalance_Watchdog_09  (09:00 daily)
echo    InnerBalance_Watchdog_21  (21:00 daily)
echo.
echo  To cancel: run cancel_scheduler.bat
echo ============================================
echo.
pause
