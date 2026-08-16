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
    return env


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
    )
