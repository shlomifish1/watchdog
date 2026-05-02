"""stop_all.py — Stop all monitored services (without restarting)."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import psutil

WATCHDOG_DIR = Path(__file__).resolve().parent
LOCKS_DIR = WATCHDOG_DIR / "locks"

try:
    from programs_config import PROGRAMS  # type: ignore
except ImportError:
    sys.path.insert(0, str(WATCHDOG_DIR))
    from programs_config import PROGRAMS  # type: ignore


def _norm(value: str | None) -> str:
    return (value or "").lower().replace("\\", "/")


def _has_process_hints(program: dict) -> bool:
    return any(
        str(program.get(key, "")).strip()
        for key in ("proc_name", "cmd_contains", "cwd_contains")
    )


def _find_matching_procs(program: dict) -> list[psutil.Process]:
    proc_name = _norm(program.get("proc_name", ""))
    cmd_contains = _norm(program.get("cmd_contains", ""))
    cwd_contains = _norm(program.get("cwd_contains", ""))

    if program["check_type"] != "process" and not _has_process_hints(program):
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


def _clear_lock(program: dict) -> None:
    key = str(program.get("key", "")).strip()
    if not key:
        return
    p = LOCKS_DIR / f"{key}.lock"
    if p.exists():
        try:
            p.unlink()
        except OSError:
            pass


def _kill_processes(program: dict) -> int:
    procs = _find_matching_procs(program)
    killed = 0
    for proc in procs:
        try:
            pid = proc.pid
            proc.kill()
            print(f"  Killed {program['name']} PID={pid}")
            killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
            print(f"  Could not kill PID={proc.pid}: {exc}")
    return killed


def _parse_excluded_keys() -> set[str]:
    raw = os.getenv("WATCHDOG_STOP_EXCLUDE_KEYS", "")
    if not raw.strip():
        return set()
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def main() -> None:
    print("=" * 50)
    print("  stop_all.py — InnerBalance Service Stop")
    print("=" * 50)

    excluded_keys = _parse_excluded_keys()
    programs = [
        program for program in PROGRAMS
        if str(program.get("key", "")).strip().lower() not in excluded_keys
    ]

    if excluded_keys:
        print(f"Excluded service keys: {', '.join(sorted(excluded_keys))}")
    print(f"Programs to stop: {len(programs)}")

    total_killed = 0
    for program in programs:
        print(f"\n[{program['name']}]")
        total_killed += _kill_processes(program)
        _clear_lock(program)

    print("\nWaiting 1 second for processes to terminate...")
    time.sleep(1)

    print("\n" + "=" * 50)
    print(f"  Killed {total_killed} process(es)")
    print("=" * 50)


if __name__ == "__main__":
    main()
