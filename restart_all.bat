@echo off
setlocal
cd /d "%~dp0"
set "WATCHDOG_RESTART_INCLUDE_KEYS=web_server,cloudflare,ai_agents_bot,whatsapp_bot"
set "WATCHDOG_RESTART_EXCLUDE_KEYS="
python "%~dp0restart_all.py"
pause
