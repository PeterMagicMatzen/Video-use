from __future__ import annotations

import json
import subprocess
from pathlib import Path

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".m4v", ".webm", ".avi"}


def find_videos(folder: Path) -> list[Path]:
    return sorted(
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in VIDEO_EXTS
    )


def _fps(rate: str | None) -> float | None:
    if not rate or rate in ("0/0", "N/A"):
        return None
    if "/" in rate:
        a, b = rate.split("/", 1)
        try:
            return float(a) / float(b)
        except (TypeError, ValueError, ZeroDivisionError):
            return None
    try:
        return float(rate)
    except (TypeError, ValueError):
        return None


def probe_source(path: Path, *, run=subprocess.run) -> dict:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-show_entries", "stream=width,height,avg_frame_rate,codec_type",
        "-of", "json",
        str(path),
    ]
    proc = run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    info = {
        "name": path.name,
        "path": str(path.resolve()),
        "duration_s": None,
        "width": None,
        "height": None,
        "fps": None,
        "error": None,
    }
    if proc.returncode != 0:
        info["error"] = (proc.stderr or "ffprobe failed")[:400]
        return info
    try:
        payload = json.loads(proc.stdout or "{}")
        dur = (payload.get("format") or {}).get("duration")
        info["duration_s"] = float(dur) if dur is not None else None
        for stream in payload.get("streams") or []:
            if stream.get("codec_type") == "video":
                info["width"] = stream.get("width")
                info["height"] = stream.get("height")
                info["fps"] = _fps(stream.get("avg_frame_rate"))
                break
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        info["error"] = str(exc)
    return info


def inventory(folder: Path, *, run=subprocess.run) -> list[dict]:
    return [probe_source(p, run=run) for p in find_videos(folder)]
