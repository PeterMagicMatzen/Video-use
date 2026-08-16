from __future__ import annotations

from pathlib import Path

from app.server.inventory import find_videos

CENTER_STATES = (
    "empty", "inventory", "transcribing", "packed",
    "strategy-ready", "rendering", "preview-ready", "stale", "error",
)


def derive_center_state(folder: Path, session: dict) -> str:
    job = session.get("job") or {}
    job_kind = job.get("kind")
    phase = job.get("phase")
    if job_kind == "transcribe" or (job_kind == "generate" and phase == "transcribe"):
        return "transcribing"
    if job_kind in {"render", "claude", "generate"}:
        return "rendering"
    if not folder.exists() or not find_videos(folder):
        return "empty"
    edit = folder / "edit"
    packed = edit / "takes_packed.md"
    edl = edit / "edl.json"
    preview = edit / "preview.mp4"
    if not packed.exists():
        return "inventory"
    if session.get("last_error") and not preview.exists():
        return "error"
    if not edl.exists():
        return "packed"
    approved_mtime = float(session.get("edl_mtime_at_approve") or 0)
    stale = bool(session.get("chat_after_approve")) or edl.stat().st_mtime > approved_mtime + 0.001
    if stale:
        return "stale"
    if not preview.exists():
        return "strategy-ready"
    return "preview-ready"
