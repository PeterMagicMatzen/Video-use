"""Start video-use as a detached process that survives the parent terminal."""

from __future__ import annotations

import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVE = ROOT / "app" / "scripts" / "serve.py"
PYW = Path(sys.executable).with_name("pythonw.exe")
if not PYW.is_file():
    PYW = Path(sys.executable)
LOG = Path.home() / ".video-use" / "server.log"
PID_FILE = Path.home() / ".video-use" / "server.pid"
HEALTH = "http://127.0.0.1:8787/api/health"


def healthy() -> bool:
    try:
        with urllib.request.urlopen(HEALTH, timeout=1.5) as response:
            return response.status == 200
    except Exception:
        return False


def _start_via_wmi() -> int:
    """Win32_Process.Create is outside the parent Job Object, so the server lives on."""
    command = f'"{PYW}" "{SERVE}"'
    ps = (
        "$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create "
        f"-Arguments @{{ CommandLine = '{command}'; CurrentDirectory = '{ROOT}' }}; "
        "Write-Output \"$($r.ReturnValue):$($r.ProcessId)\""
    )
    done = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    line = (done.stdout or "").strip().splitlines()[-1] if done.stdout else ""
    if ":" not in line:
        raise RuntimeError((done.stderr or done.stdout or "wmi create failed")[-400:])
    code, pid = line.split(":", 1)
    if code != "0" or not pid.isdigit():
        raise RuntimeError(f"wmi create failed rv={code} pid={pid} {done.stderr}")
    return int(pid)


def start() -> None:
    if healthy():
        print("already-running")
        return

    LOG.parent.mkdir(parents=True, exist_ok=True)
    try:
        pid = _start_via_wmi()
    except Exception as exc:
        print(f"wmi start failed: {exc}", file=sys.stderr)
        sys.exit(1)
    PID_FILE.write_text(str(pid), encoding="utf-8")
    for _ in range(40):
        if healthy():
            print(f"started {pid}")
            return
        time.sleep(0.25)
    tail = LOG.read_text(encoding="utf-8", errors="replace")[-800:] if LOG.is_file() else ""
    print(f"timeout waiting for /api/health\n{tail}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    start()
