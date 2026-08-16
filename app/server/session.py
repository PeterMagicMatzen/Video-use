from __future__ import annotations

import json
import os
from pathlib import Path

JOB_KINDS = ("idle", "transcribe", "claude", "render")


def default_session(folder: Path) -> dict:
    return {
        "claude_session_id": None,
        "folder": str(folder.resolve()),
        "edl_approved_at": None,
        "edl_mtime_at_approve": 0,
        "last_error": None,
        "job": {"kind": "idle", "pid": None, "started_at": None, "output": None, "log": None},
    }


def session_path(folder: Path) -> Path:
    return folder / "edit" / "app_session.json"


def load_session(folder: Path) -> dict:
    path = session_path(folder)
    if not path.exists():
        return default_session(folder)
    data = json.loads(path.read_text(encoding="utf-8"))
    base = default_session(folder)
    base.update(data)
    if not isinstance(base.get("job"), dict):
        base["job"] = default_session(folder)["job"]
    return reclaim_job(base, folder)


def save_session(folder: Path, data: dict) -> None:
    path = session_path(folder)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    if os.name == "nt":
        return _pid_alive_windows(int(pid))
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _pid_alive_windows(pid: int) -> bool:
    """os.kill(pid, 0) is not a liveness check on Windows (WinError 87)."""
    import ctypes
    kernel32 = ctypes.windll.kernel32
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if handle:
        kernel32.CloseHandle(handle)
        return True
    # 5 = ACCESS_DENIED: process exists
    return kernel32.GetLastError() == 5


_FRIENDLY_STOP = {
    "transcribe": "Captions stopped. Tap Generate to try again.",
    "claude": "Directing stopped. Tap Generate to try again.",
    "render": "Export stopped. Tap Generate to try again.",
    "generate": "Generate stopped. Tap Generate to try again.",
}


def reclaim_job(data: dict, folder: Path | None = None) -> dict:
    job = data.get("job") or {}
    kind = job.get("kind") or "idle"
    if kind == "idle":
        return data
    worker = job.get("worker_pid") or job.get("pid")
    tracked = job.get("pid")
    if (worker and pid_alive(int(worker))) or (tracked and pid_alive(int(tracked))):
        return data
    # Process is gone. If we already have a finished preview from this pass, stay quiet.
    if folder is not None:
        preview = folder / "edit" / "preview.mp4"
        if preview.is_file() and kind in {"render", "generate", "claude"}:
            data["job"] = {"kind": "idle", "pid": None, "started_at": None, "output": None, "log": None}
            if data.get("last_error") and "pid" in str(data.get("last_error")).lower():
                data["last_error"] = None
            return data
    # Worker is gone. Idle the job but do not invent a "Directing stopped"
    # banner — that raced Generate and hid the real error (wrong transcript).
    data["job"] = {"kind": "idle", "pid": None, "started_at": None, "output": None, "log": None}
    return data
