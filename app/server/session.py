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
    return reclaim_job(base)


def save_session(folder: Path, data: dict) -> None:
    path = session_path(folder)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def reclaim_job(data: dict) -> dict:
    job = data.get("job") or {}
    kind = job.get("kind") or "idle"
    pid = job.get("pid")
    if kind != "idle" and pid and not pid_alive(int(pid)):
        data["last_error"] = f"previous {kind} job died (pid {pid})"
        data["job"] = {"kind": "idle", "pid": None, "started_at": None, "output": None, "log": None}
    return data
