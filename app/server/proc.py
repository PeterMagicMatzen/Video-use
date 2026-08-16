from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from app.server.paths import HELPERS


def helper_env() -> dict:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    return env


CREATE_BREAKAWAY_FROM_JOB = 0x01000000
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000


def _pythonw(cmd: list[str]) -> list[str]:
    out = list(cmd)
    if not out:
        return out
    exe = Path(str(out[0]))
    if exe.name.lower() == "python.exe":
        pyw = exe.with_name("pythonw.exe")
        if pyw.is_file():
            out[0] = str(pyw)
    return out


def spawn_detached(cmd: list[str], *, cwd: Path | None = None, log: Path | None = None) -> int:
    """Start a child that is not on this console and not in the parent Job Object."""
    cmd = _pythonw(cmd)
    if log is not None:
        log.parent.mkdir(parents=True, exist_ok=True)
        out = open(log, "a", encoding="utf-8")
    else:
        out = subprocess.DEVNULL
    flags = CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW | CREATE_BREAKAWAY_FROM_JOB
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd) if cwd else None,
            stdout=out,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            creationflags=flags,
            close_fds=True,
        )
    except OSError:
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd) if cwd else None,
            stdout=out,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            creationflags=CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW,
            close_fds=True,
        )
    return proc.pid


def run_helper(script: str, args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess:
    exe = sys.executable or "python"
    cmd = [exe, str(HELPERS / script), *args]
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=helper_env(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP,
    )
