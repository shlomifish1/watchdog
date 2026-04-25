"""InnerBalance Watchdog - monitors services, auto-restarts on failure, kills duplicates."""

from __future__ import annotations

import logging
import logging.handlers
import os
import http.server
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
import json as _json
import threading as _threading

import psutil
import requests
try:
    from dotenv import load_dotenv as _load_dotenv  # type: ignore
except Exception:
    _load_dotenv = None

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
WATCHDOG_DIR = Path(__file__).resolve().parent
LOCKS_DIR = WATCHDOG_DIR / "locks"
LOG_FILE = WATCHDOG_DIR / "watchdog.log"
CHECK_INTERVAL_SECONDS = 30
WATCHDOG_API_PORT = 9999

_CENTRAL_ENV = WATCHDOG_DIR.parent / "_config" / ".env"
if _load_dotenv and _CENTRAL_ENV.exists():
    _load_dotenv(dotenv_path=str(_CENTRAL_ENV), override=True)

PROMPT_COOLDOWN_SECONDS = int(os.getenv("WATCHDOG_PROMPT_COOLDOWN_SECONDS", "300"))
ENABLE_POPUP_PROMPTS = os.getenv("WATCHDOG_ENABLE_POPUP", "1").strip().lower() not in {"0", "false", "no"}
ENABLE_TELEGRAM_PROMPTS = os.getenv("WATCHDOG_ENABLE_TELEGRAM", "1").strip().lower() not in {"0", "false", "no"}

WATCHDOG_TELEGRAM_TOKEN = (
    os.getenv("WATCHDOG_TELEGRAM_BOT_TOKEN", "").strip()
    or os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
)
WATCHDOG_TELEGRAM_CHAT_ID = (
    os.getenv("WATCHDOG_TELEGRAM_CHAT_ID", "").strip()
    or os.getenv("ADMIN_ID", "").strip()
)
AUTO_RESTART_NO_CONFIRM_KEYS = {
    item.strip()
    for item in os.getenv(
        "WATCHDOG_AUTO_RESTART_NO_CONFIRM_KEYS",
        "ai_agents_bot,bot_news",
    ).split(",")
    if item.strip()
}
_RESTART_HOLD_UNTIL: dict[str, float] = {}

# ---------------------------------------------------------------------------
# Logging (rotating at 5 MB)
# ---------------------------------------------------------------------------
_handler = logging.handlers.RotatingFileHandler(
    str(LOG_FILE),
    maxBytes=5 * 1024 * 1024,
    backupCount=3,
    encoding="utf-8",
)
_handler.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s"))

log = logging.getLogger("watchdog")
log.setLevel(logging.INFO)
log.addHandler(_handler)
# Only add console handler if stdout exists (pythonw.exe has sys.stdout=None)
if sys.stdout is not None:
    _console = logging.StreamHandler(sys.stdout)
    _console.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s"))
    log.addHandler(_console)

# ---------------------------------------------------------------------------
# Programs list (single source of truth)
# ---------------------------------------------------------------------------
try:
    from programs_config import PROGRAMS  # type: ignore
except ImportError:
    # Fallback inline copy if programs_config.py is not on the path
    sys.path.insert(0, str(WATCHDOG_DIR))
    from programs_config import PROGRAMS  # type: ignore


# ---------------------------------------------------------------------------
# Helpers â€“ process detection
# ---------------------------------------------------------------------------

def _norm(value: str | None) -> str:
    return (value or "").lower().replace("\\", "/")


def _find_matching_procs(program: dict) -> list[psutil.Process]:
    """Return all live processes that match the program's check criteria."""
    matches: list[psutil.Process] = []
    for proc in psutil.process_iter(["pid", "name", "cmdline", "create_time"]):
        try:
            if _proc_matches_program(proc, program):
                matches.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            continue
    return matches


def _has_process_hints(program: dict) -> bool:
    return any(
        str(program.get(key, "")).strip()
        for key in ("proc_name", "cmd_contains", "cwd_contains")
    )


def _proc_matches_program(proc: psutil.Process, program: dict) -> bool:
    """Best-effort matcher for one process against one program definition."""
    proc_name = _norm(program.get("proc_name", ""))
    cmd_contains = _norm(program.get("cmd_contains", ""))
    cwd_contains = _norm(program.get("cwd_contains", ""))
    pinfo = getattr(proc, "info", None) or {}
    pname = _norm(pinfo.get("name") or proc.name() or "")
    cmdline_parts = pinfo.get("cmdline") or proc.cmdline() or []
    cmdline = _norm(" ".join(cmdline_parts))

    if proc_name and proc_name not in pname and proc_name not in cmdline:
        return False
    if cmd_contains and cmd_contains not in cmdline:
        return False
    if cwd_contains:
        try:
            cwd = _norm(proc.cwd())
        except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
            cwd = ""
        if cwd_contains not in cwd and cwd_contains not in cmdline:
            return False
    return True


def _check_url(url: str) -> bool:
    try:
        resp = requests.get(url, timeout=4)
        return resp.status_code == 200
    except Exception:
        return False


def _is_running(program: dict) -> bool:
    if program["check_type"] == "url":
        return _check_url(program["url"])
    if program["check_type"] == "process":
        # Prefer lock PID if it still points to a matching live process.
        key = str(program.get("key", ""))
        lock_pid = _read_lock(key) if key else None
        if lock_pid:
            try:
                lock_proc = psutil.Process(lock_pid)
                if lock_proc.is_running() and _proc_matches_program(lock_proc, program):
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                pass
        return len(_find_matching_procs(program)) > 0
    return False


def _status_icon(is_up: bool) -> str:
    return "âœ…" if is_up else "âŒ"


def _telegram_notify(text: str) -> None:
    if not ENABLE_TELEGRAM_PROMPTS:
        return
    if not WATCHDOG_TELEGRAM_TOKEN or not WATCHDOG_TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{WATCHDOG_TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": WATCHDOG_TELEGRAM_CHAT_ID, "text": text},
            timeout=10,
        )
    except Exception as exc:
        log.warning("Telegram notify failed: %s", exc)


def _popup_yes_no(title: str, message: str) -> bool:
    """Show blocking Yes/No popup on Windows. Returns True for Yes."""
    if os.name != "nt" or not ENABLE_POPUP_PROMPTS:
        return False
    try:
        import ctypes

        MB_YESNO = 0x00000004
        MB_ICONQUESTION = 0x00000020
        MB_TOPMOST = 0x00040000
        IDYES = 6
        result = ctypes.windll.user32.MessageBoxW(None, message, title, MB_YESNO | MB_ICONQUESTION | MB_TOPMOST)
        return result == IDYES
    except Exception as exc:
        log.warning("Popup prompt failed: %s", exc)
        return False


def _confirm_restart_with_user(program: dict, reason: str) -> bool:
    """Ask the operator before restarting a service (popup + Telegram)."""
    name = str(program.get("name", program.get("key", "service")))
    key = str(program.get("key", "unknown"))
    message = (
        f"Watchdog alert\n"
        f"Service: {name} ({key})\n"
        f"Reason: {reason}\n\n"
        f"×”×× ×œ×”×¨×™× ×ž×—×“×©?"
    )
    _telegram_notify(f"âš ï¸ {message}")
    approved = _popup_yes_no("InnerBalance Watchdog", message)
    _telegram_notify(
        f"{'âœ…' if approved else 'â¸ï¸'} ×”×—×œ×˜×” ×ž×§×•×ž×™×ª ×¢×‘×•×¨ {name} ({key}): "
        f"{'×œ×”×¨×™× ×ž×—×“×©' if approved else '×œ× ×œ×”×¨×™× ×›×¨×’×¢'}"
    )
    return approved


def _requires_operator_confirmation(program: dict) -> bool:
    key = str(program.get("key", "")).strip()
    return key not in AUTO_RESTART_NO_CONFIRM_KEYS


def _startup_relaunch_confirmation() -> None:
    """
    On watchdog startup:
    If a always-on service is already running, ask whether to relaunch it.
    """
    for program in PROGRAMS:
        if program.get("lazy", False) or not program.get("auto_restart", False):
            continue
        if not _requires_operator_confirmation(program):
            continue
        if not _is_running(program):
            continue
        if _confirm_restart_with_user(program, "already active at watchdog startup"):
            ok, message = restart_service_by_key(program["key"], send_notifications=False)
            log.info(message)
            _telegram_notify(f"{'âœ…' if ok else 'âŒ'} {message}")
        else:
            log.info("Operator declined relaunch for %s on startup.", program["name"])


class WatchdogAPIHandler(http.server.BaseHTTPRequestHandler):
    """Minimal HTTP API for watchdog."""

    def log_message(self, format, *args):  # noqa: A003
        pass

    def _send_json(self, data: dict, status: int = 200) -> None:
        body = _json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        # GET /status -> all programs
        # GET /status/<key> -> one program
        if self.path == "/status":
            statuses: dict[str, bool] = {}
            for prog in PROGRAMS:
                statuses[prog["key"]] = _check_program_alive(prog)
            self._send_json({"ok": True, "services": statuses})
        elif self.path.startswith("/status/"):
            key = self.path[8:]
            prog = next((p for p in PROGRAMS if p["key"] == key), None)
            if prog is None:
                self._send_json({"ok": False, "error": "unknown service"}, 404)
            else:
                alive = _check_program_alive(prog)
                self._send_json({"ok": True, "key": key, "alive": alive})
        else:
            self._send_json({"ok": False, "error": "not found"}, 404)

    def do_POST(self) -> None:
        # POST /start/<key> -> on-demand start if not running
        if self.path.startswith("/start/"):
            key = self.path[7:]
            prog = next((p for p in PROGRAMS if p["key"] == key), None)
            if prog is None:
                self._send_json({"ok": False, "error": "unknown service"}, 404)
                return

            alive = _check_program_alive(prog)
            if alive:
                self._send_json({"ok": True, "key": key, "action": "already_running"})
                return

            started = _start_program(prog)
            self._send_json(
                {
                    "ok": True,
                    "key": key,
                    "action": "started" if started else "failed",
                }
            )
        else:
            self._send_json({"ok": False, "error": "not found"}, 404)


def _check_program_alive(prog: dict) -> bool:
    """Returns True if the program appears to be running."""
    check_type = prog.get("check_type", "process")
    if check_type == "url":
        try:
            response = requests.get(str(prog["url"]), timeout=1)
            return response.status_code == 200
        except Exception:
            return False
    return len(_find_matching_procs(prog)) > 0


def _start_watchdog_api(port: int = WATCHDOG_API_PORT) -> None:
    """Start the watchdog HTTP API in a background daemon thread."""
    server = http.server.HTTPServer(("127.0.0.1", int(port)), WatchdogAPIHandler)
    t = _threading.Thread(target=server.serve_forever, daemon=True, name="watchdog-api")
    t.start()
    log.info("Watchdog HTTP API listening on http://127.0.0.1:%d", int(port))


def collect_service_statuses() -> list[dict[str, Any]]:
    statuses: list[dict[str, Any]] = []
    for program in PROGRAMS:
        statuses.append(
            {
                "key": program["key"],
                "name": program["name"],
                "button": program.get("button", program["name"]),
                "up": _is_running(program),
                "check_type": program["check_type"],
            }
        )
    return statuses


def format_system_status_message(statuses: list[dict[str, Any]] | None = None, *, header: str = "System Status") -> str:
    rows = statuses or collect_service_statuses()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    down_count = sum(1 for item in rows if not item["up"])
    lines = [header, now, ""]
    for item in rows:
        lines.append(f"{_status_icon(item['up'])} {item['name']}")
    lines.append("")
    if down_count:
        lines.append(f"Down right now: {down_count}")
    else:
        lines.append("All monitored services are up.")
    return "\n".join(lines)


def build_action_rows(statuses: list[dict[str, Any]] | None = None) -> list[list[tuple[str, str]]]:
    rows = statuses or collect_service_statuses()
    buttons: list[list[tuple[str, str]]] = []
    for item in rows:
        if not item["up"]:
            buttons.append([(f"Start {item['button']}", f"systems_restart:{item['key']}")])
    buttons.append([("Refresh status", "systems_refresh")])
    return buttons


def restart_service_by_key(service_key: str, send_notifications: bool = True) -> tuple[bool, str]:
    service = next((item for item in PROGRAMS if item["key"] == service_key), None)
    if not service:
        message = f"Unknown service: {service_key}"
        log.warning(message)
        return False, message

    if service["check_type"] == "process" or _has_process_hints(service):
        for proc in _find_matching_procs(service):
            try:
                proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        time.sleep(1)

    ok = _start_program(service)
    message = f"Restarted: {service['name']}" if ok else f"Failed to restart: {service['name']}"
    if send_notifications:
        log.info(message)
    return ok, message


# ---------------------------------------------------------------------------
# Lock files
# ---------------------------------------------------------------------------

def _lock_path(key: str) -> Path:
    return LOCKS_DIR / f"{key}.lock"


def _read_lock(key: str) -> int | None:
    p = _lock_path(key)
    if not p.exists():
        return None
    try:
        pid_str = p.read_text(encoding="utf-8", errors="ignore").strip()
        pid = int(pid_str)
        return pid if pid > 0 else None
    except Exception:
        return None


def _write_lock(key: str, pid: int) -> None:
    LOCKS_DIR.mkdir(parents=True, exist_ok=True)
    _lock_path(key).write_text(str(pid), encoding="utf-8")


def _clear_lock(key: str) -> None:
    p = _lock_path(key)
    if p.exists():
        try:
            p.unlink()
        except Exception:
            pass


def _lock_is_alive(key: str) -> bool:
    pid = _read_lock(key)
    if pid is None:
        return False
    return psutil.pid_exists(pid)


# ---------------------------------------------------------------------------
# Start a program
# ---------------------------------------------------------------------------

def _start_program(program: dict) -> bool:
    key = program["key"]
    name = program["name"]
    bat = Path(program["start_bat"])
    cwd = Path(program.get("start_cwd", bat.parent))

    if not bat.exists():
        log.warning("Launcher not found for %s: %s", name, bat)
        return False

    if _lock_is_alive(key):
        log.info("Lock alive for %s â€” skip start", name)
        return False

    try:
        si = None
        flags = 0
        if os.name == "nt":
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 0
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)

        proc = subprocess.Popen(
            ["cmd", "/c", str(bat)],
            cwd=str(cwd),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            startupinfo=si,
            creationflags=flags,
        )
        if program["check_type"] == "process":
            bot_pid = None
            for _ in range(20):
                procs = _find_matching_procs(program)
                if procs:
                    try:
                        newest = max(procs, key=lambda p: p.create_time())
                        bot_pid = newest.pid
                        _write_lock(key, bot_pid)
                        break
                    except Exception:
                        pass
                time.sleep(1)

            if bot_pid is None:
                log.warning(
                    "Could not resolve %s bot PID after launcher start; keeping launcher PID=%d",
                    name,
                    proc.pid,
                )
                _write_lock(key, proc.pid)
                log.info("Restarted: %s (launcher PID=%d)", name, proc.pid)
            else:
                log.info(
                    "Restarted: %s (bot PID=%d, launcher PID=%d)",
                    name,
                    bot_pid,
                    proc.pid,
                )
        else:
            _write_lock(key, proc.pid)
            log.info("Restarted: %s (launcher PID=%d)", name, proc.pid)
        return True
    except Exception as exc:
        log.error("Failed to start %s: %s", name, exc)
        return False


# ---------------------------------------------------------------------------
# Kill duplicates
# ---------------------------------------------------------------------------

def _kill_duplicates(program: dict) -> None:
    """If more than one matching process is running, kill older ones (keep newest)."""
    if program["check_type"] != "process" and not _has_process_hints(program):
        return

    procs = _find_matching_procs(program)
    if len(procs) <= 1:
        return

    # Sort by create_time ascending; oldest first
    try:
        procs.sort(key=lambda p: p.create_time())
    except Exception:
        return

    # Keep the LAST (newest); kill the rest
    to_kill = procs[:-1]
    for p in to_kill:
        try:
            pid = p.pid
            p.kill()
            log.info("Killed duplicate: %s  PID=%d", program["name"], pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
            log.warning("Could not kill duplicate PID=%d: %s", p.pid, exc)


# ---------------------------------------------------------------------------
# Main check loop
# ---------------------------------------------------------------------------

def _another_watchdog_alive() -> bool:
    """Return True if another watchdog process is confirmed running (checks both PID and cmdline)."""
    existing_pid = _read_lock("watchdog")
    if existing_pid is None or existing_pid <= 0:
        return False
    if existing_pid == os.getpid():
        return False
    try:
        p = psutil.Process(existing_pid)
        cmdline = " ".join(p.cmdline())
        # Verify it's actually a watchdog, not a recycled PID
        return "watchdog.py" in cmdline and "python" in p.name().lower()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


def run_once() -> None:
    log.info("--- watchdog check ---")
    now = time.time()
    for program in PROGRAMS:
        if program.get("lazy", False) or not program.get("auto_restart", True):
            continue

        key = program["key"]
        name = program["name"]

        # 1) Optionally kill duplicates first.
        if (program["check_type"] == "process" or _has_process_hints(program)) and program.get("kill_duplicates", True):
            _kill_duplicates(program)

        # 2) Check if running

        if _is_running(program):
            _RESTART_HOLD_UNTIL.pop(key, None)
            if program["check_type"] == "process" or _has_process_hints(program):
                procs = _find_matching_procs(program)
                if procs:
                    try:
                        newest = max(procs, key=lambda p: p.create_time())
                        _write_lock(key, newest.pid)
                    except Exception:
                        pass
            continue

        hold_until = _RESTART_HOLD_UNTIL.get(key, 0)
        if now < hold_until:
            continue

        if _requires_operator_confirmation(program):
            log.warning("DOWN: %s - awaiting operator confirmation for restart", name)
            approved = _confirm_restart_with_user(program, "service is down")
            if not approved:
                _RESTART_HOLD_UNTIL[key] = now + PROMPT_COOLDOWN_SECONDS
                log.info("Operator declined restart for %s. Next prompt in %ds.", name, PROMPT_COOLDOWN_SECONDS)
                continue
        else:
            log.warning("DOWN: %s - restarting automatically (no-confirm policy)", name)

        started = _start_program(program)
        if started:
            _RESTART_HOLD_UNTIL.pop(key, None)
            if key in AUTO_RESTART_NO_CONFIRM_KEYS:
                log.info("Auto-restart success (quiet notify policy): %s (%s)", name, key)
            else:
                _telegram_notify(f"✅ שירות עלה מחדש: {name} ({key})")
        else:
            _RESTART_HOLD_UNTIL[key] = now + PROMPT_COOLDOWN_SECONDS
            _telegram_notify(f"❌ כשל בהעלאה מחדש של: {name} ({key})")

def main() -> None:
    LOCKS_DIR.mkdir(parents=True, exist_ok=True)
    # Exit silently if another instance is already running
    if _another_watchdog_alive():
        return
    # Claim the lock
    _write_lock("watchdog", os.getpid())
    log.info("InnerBalance Watchdog started. PID=%d Interval=%ds", os.getpid(), CHECK_INTERVAL_SECONDS)
    _start_watchdog_api(WATCHDOG_API_PORT)
    # Run startup confirmation flow in background so watchdog API/loop are not blocked by popup dialogs.
    _threading.Thread(
        target=_startup_relaunch_confirmation,
        daemon=True,
        name="startup-relaunch-confirmation",
    ).start()
    while True:
        try:
            run_once()
        except Exception as exc:
            log.exception("Unexpected error in watchdog loop: %s", exc)
        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()

