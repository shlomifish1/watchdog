"""restart_all.py — Kill all instances of every monitored program, then start each one fresh."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import psutil

WATCHDOG_DIR = Path(__file__).resolve().parent

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
    """Return all live processes that match the program's check criteria."""
    proc_name = _norm(program.get("proc_name", ""))
    cmd_contains = _norm(program.get("cmd_contains", ""))
    cwd_contains = _norm(program.get("cwd_contains", ""))

    if program["check_type"] != "process" and not _has_process_hints(program):
        return []

    matches: list[psutil.Process] = []
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            pname = _norm(proc.info.get("name") or "")
            cmdline_parts = proc.info.get("cmdline") or []
            cmdline = _norm(" ".join(cmdline_parts))

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


def _kill_all(program: dict) -> int:
    """Kill all matching processes. Returns count killed."""
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


def _start_program(program: dict) -> bool:
    name = program["name"]
    bat = Path(program["start_bat"])
    cwd = Path(program.get("start_cwd", bat.parent))

    if not bat.exists():
        print(f"  WARNING: launcher not found for {name}: {bat}")
        return False

    try:
        si = None
        flags = 0
        if os.name == "nt":
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 0
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        subprocess.Popen(
            ["cmd", "/c", str(bat)],
            cwd=str(cwd),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            startupinfo=si,
            creationflags=flags,
        )
        print(f"  Started: {name}")
        return True
    except Exception as exc:
        print(f"  ERROR starting {name}: {exc}")
        return False


def main() -> None:
    print("=" * 50)
    print("  restart_all.py — InnerBalance Service Restart")
    print("=" * 50)

    started = 0
    for program in PROGRAMS:
        print(f"\n[{program['name']}]")

        # Kill all existing instances
        _kill_all(program)

    # Wait for processes to die
    print("\nWaiting 2 seconds for processes to terminate...")
    time.sleep(2)

    # Start each program fresh
    for program in PROGRAMS:
        print(f"\n[{program['name']}]")
        ok = _start_program(program)
        if ok:
            started += 1

    print("\n" + "=" * 50)
    print(f"  Restarted {started} programs")
    print("=" * 50)


if __name__ == "__main__":
    main()
