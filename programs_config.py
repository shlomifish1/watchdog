"""Shared program definitions for watchdog and restart logic."""

from pathlib import Path

DESKTOP = Path("C:/Users/fishman-ai-server/Desktop")
AI_AGENTS_DIR = DESKTOP / "ai_agents"
DELIVERY_HSP_DIR = DESKTOP / "delivery_hsp"
BOT_NEWS_DIR = DESKTOP / "bot_news"
MARKETING_WORKFLOW_DIR = DESKTOP / "marketing_workflow_app"
MEDIA_WORKFLOW_DIR = DESKTOP / "media_workflow_app"
# PHASE 5: numerology lives here after extraction.
NUMEROLOGY_DIR = DESKTOP / "numerology_app"
FINANCE_WORKFLOW_DIR = DESKTOP / "finance_workflow_app"

PROGRAMS = [
    # Chrome with CDP (required for War Room / Mastermind Agent)
    {
        "name": "Chrome (CDP port 9222)",
        "key": "chrome_cdp",
        "check_type": "process",
        "proc_name": "chrome",
        "cmd_contains": "remote-debugging-port",
        "cwd_contains": "",
        "start_bat": str(AI_AGENTS_DIR / "start_chrome_cdp.bat"),
        "start_cwd": str(AI_AGENTS_DIR),
        "auto_restart": False,
        "lazy": False,
    },
    # Always on (auto-start at boot)
    {
        "name": "Web Server (InnerBalance)",
        "key": "web_server",
        "check_type": "url",
        "url": "http://127.0.0.1:8000/healthz",
        "proc_name": "python",
        "cmd_contains": "web_server.py",
        "cwd_contains": "ai_agents",
        "start_bat": str(AI_AGENTS_DIR / "start_web_server_only.bat"),
        "start_cwd": str(AI_AGENTS_DIR),
        "auto_restart": True,
        "lazy": False,
    },
    {
        "name": "Cloudflare Tunnel",
        "key": "cloudflare",
        "check_type": "process",
        "proc_name": "cloudflared",
        "cmd_contains": "",
        "cwd_contains": "",
        "start_bat": str(AI_AGENTS_DIR / "start_cloudflare_tunnel_only.bat"),
        "start_cwd": str(AI_AGENTS_DIR),
        "auto_restart": True,
        "lazy": False,
    },
    # Always on (live services)
    {
        "name": "AI Agents Bot (Telegram)",
        "key": "ai_agents_bot",
        "check_type": "process",
        "proc_name": "python",
        "cmd_contains": "main.py",
        "cwd_contains": "ai_agents",
        "start_bat": str(AI_AGENTS_DIR / "start_ai_agents_bot_only.bat"),
        "start_cwd": str(AI_AGENTS_DIR),
        "auto_restart": True,
        "lazy": False,
        "kill_duplicates": False,
    },
    {
        "name": "WhatsApp Bot",
        "key": "whatsapp_bot",
        "check_type": "process",
        "proc_name": "node",
        "cmd_contains": "index.js",
        "cwd_contains": "whatsapp_bot",
        "start_bat": str(AI_AGENTS_DIR / "whatsapp_bot" / "start_whatsapp_bot.bat"),
        "start_cwd": str(AI_AGENTS_DIR / "whatsapp_bot"),
        "auto_restart": False,
        "lazy": True,
        "kill_duplicates": False,
    },
    {
        "name": "Delivery HSP Bot",
        "key": "delivery_hsp_bot",
        "check_type": "process",
        "proc_name": "python",
        "cmd_contains": "main.py",
        "cwd_contains": "delivery_hsp",
        "start_bat": str(DELIVERY_HSP_DIR / "run_forever.bat"),
        "start_cwd": str(DELIVERY_HSP_DIR),
        "auto_restart": False,
        "lazy": True,
    },
    {
        "name": "News Bot",
        "key": "bot_news",
        "check_type": "process",
        "proc_name": "python",
        "cmd_contains": "main.py",
        "cwd_contains": "bot_news",
        "start_bat": str(BOT_NEWS_DIR / "start_bot_only.bat"),
        "start_cwd": str(BOT_NEWS_DIR),
        "auto_restart": True,
        "lazy": False,
        "kill_duplicates": False,
    },
    # On-demand only (lazy start)
    {
        "name": "Marketing Workflow App",
        "key": "marketing_workflow",
        "check_type": "url",
        "url": "http://127.0.0.1:8200/health",
        "start_bat": str(MARKETING_WORKFLOW_DIR / "start_api_only.bat"),
        "start_cwd": str(MARKETING_WORKFLOW_DIR),
        "auto_restart": False,
        "lazy": True,
    },
    {
        "name": "Media Workflow App",
        "key": "media_workflow",
        "check_type": "url",
        "url": "http://127.0.0.1:8100/health",
        "start_bat": str(MEDIA_WORKFLOW_DIR / "run_backend_only.bat"),
        "start_cwd": str(MEDIA_WORKFLOW_DIR),
        "auto_restart": False,
        "lazy": True,
    },
    # Cabinet Bot removed; it is started from ai_agents startup.
    {
        "name": "Numerology App",
        "key": "numerology_app",
        "check_type": "url",
        "url": "http://127.0.0.1:8300/healthz",
        "start_bat": str(NUMEROLOGY_DIR / "start.bat"),
        "start_cwd": str(NUMEROLOGY_DIR),
        "auto_restart": False,
        "lazy": True,
    },
    {
        "name": "Finance Workflow App",
        "key": "finance_workflow",
        "check_type": "url",
        "url": "http://127.0.0.1:8400/finance/api/health",
        "proc_name": "python",
        "cmd_contains": "uvicorn",
        "cwd_contains": "finance_workflow_app",
        "start_bat": str(FINANCE_WORKFLOW_DIR / "start.bat"),
        "start_cwd": str(FINANCE_WORKFLOW_DIR),
        "auto_restart": True,
        "lazy": False,
    },
]
