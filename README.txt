InnerBalance OS - Watchdog
==========================

What this folder does
---------------------
- Runs scheduled health checks for the main local services.
- Sends Telegram alerts when a monitored service is down.
- Exposes helper functions for the main InnerBalance bot `/systems` command.

Recommended Telegram control path
---------------------------------
- Use `/systems` inside the main InnerBalance bot.
- The bot shows current service status and restart buttons per service.
- This avoids conflicts from two different processes polling the same Telegram bot token.

Optional dedicated watchdog bot
-------------------------------
- If you define `WATCHDOG_TELEGRAM_BOT_TOKEN`, watchdog can run its own listener mode.
- Start it with: `python watchdog.py --listen`
- Without a dedicated token, watchdog should not run a persistent Telegram listener while the main bot is alive.

Monitored services
------------------
- `web_server` -> `ai_agents/web_server.py`
- `cloudflare` -> `cloudflared tunnel`
- `ai_agents_bot` -> `ai_agents/main.py`
- `cabinet_bot` -> `real_agents_bot/main.py`
- `bot_news` -> `bot_news/main.py`
- `marketing_workflow` -> `http://127.0.0.1:8200/health`
- `media_workflow` -> `http://127.0.0.1:8100/health`

Files in this folder
--------------------
- `watchdog.py` -> main watchdog logic
- `check_now.bat` -> run one manual check now
- `watchdog_run.bat` -> non-interactive scheduled run
- `setup_scheduler.bat` -> create scheduled tasks
- `cancel_scheduler.bat` -> remove scheduled tasks

Notes
-----
- Each monitored service now has its own dedicated restart BAT file.
- The main Telegram bot handles `/systems`; watchdog focuses on health checks and restart helpers.
- If you want proactive alerts more often than twice daily, adjust the scheduler frequency.
