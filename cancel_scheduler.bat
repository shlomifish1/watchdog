@echo off
title InnerBalance - Cancel Scheduler

echo.
echo Removing scheduled watchdog tasks...
echo.

schtasks /delete /tn "InnerBalance_Watchdog_09" /f
schtasks /delete /tn "InnerBalance_Watchdog_21" /f

echo.
echo Done. Watchdog will no longer run automatically.
echo.
pause
