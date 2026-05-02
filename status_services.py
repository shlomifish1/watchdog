"""Print current runtime status for monitored services."""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import psutil

WATCHDOG_DIR = Path(__file__).resolve().parent

try:
    from programs_config import PROGRAMS  # type: ignore
except ImportError:
    sys.path.insert(0, str(WATCHDOG_DIR))
    from programs_config import PROGRAMS  # type: ignore


def _norm(value: str | None) -> str:
    return (value or "").lower().replace("\\", "/")


def _find_matching_procs(program: dict) -> list[psutil.Process]:
    proc_name = _norm(program.get("proc_name", ""))
    cmd_contains = _norm(program.get("cmd_contains", ""))
    cwd_contains = _norm(program.get("cwd_contains", ""))
    if not (proc_name or cmd_contains or cwd_contains):
        return []

    matches: list[psutil.Process] = []
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            pname = _norm(proc.info.get("name") or "")
            cmdline = _norm(" ".join(proc.info.get("cmdline") or []))
            if proc_name and proc_name not in pname and proc_name not in cmdline:
                continue
            if cmd_contains and cmd_contains not in cmdline:
                continue
            if cwd_contains:
                try:
                    cwd = _norm(proc.cwd())
                except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
                    cwd = ""
                if cwd_contains not in cwd and cwd_contains not in cmdline:
                    continue
            matches.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            continue
    return matches


def _url_ok(url: str) -> bool:
    try:
        with urlopen(url, timeout=0.8) as resp:
            code = int(getattr(resp, "status", 0) or 0)
            return 200 <= code < 400
    except (URLError, TimeoutError, ValueError):
        return False


def _mb(value: int) -> str:
    return f"{(value / (1024 * 1024)):.1f} MB"


def main() -> None:
    rows: list[tuple[str, str, str, str, str]] = []
    for program in PROGRAMS:
        name = str(program.get("name", "service"))
        key = str(program.get("key", ""))
        procs = _find_matching_procs(program)
        pids = sorted({int(proc.pid) for proc in procs})
        rss = 0
        for proc in procs:
            try:
                rss += int(proc.memory_info().rss or 0)
            except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                continue
        if pids:
            status = "RUNNING"
        elif str(program.get("check_type", "")).lower() == "url":
            status = "UP" if _url_ok(str(program.get("url", ""))) else "DOWN"
        else:
            status = "DOWN"
        rows.append((name, key, status, ",".join(str(pid) for pid in pids) or "-", _mb(rss)))

    print("=" * 120)
    print(f"{'Service':40} {'Key':20} {'Status':8} {'PIDs':25} {'RAM':12}")
    print("-" * 120)
    for row in rows:
        print(f"{row[0]:40} {row[1]:20} {row[2]:8} {row[3]:25} {row[4]:12}")
    print("=" * 120)


if __name__ == "__main__":
    main()
