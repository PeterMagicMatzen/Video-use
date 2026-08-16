"""User-added B-roll, graphics, and voice clips living under edit/bin/."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

KINDS = ("broll", "graphic", "voice", "sfx")
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".ogg"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".m4v", ".webm", ".avi"}


def bin_path(edit_dir: Path) -> Path:
    return edit_dir / "bin.json"


def load_bin(edit_dir: Path) -> list[dict]:
    path = bin_path(edit_dir)
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def save_bin(edit_dir: Path, items: list[dict]) -> None:
    bin_path(edit_dir).write_text(json.dumps(items, indent=2), encoding="utf-8")


def probe_duration(path: Path) -> float:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    try:
        return max(0.4, float((proc.stdout or "2").strip()))
    except ValueError:
        return 2.0


def add_item(edit_dir: Path, kind: str, src: Path) -> dict:
    if kind not in KINDS:
        raise ValueError(f"unknown bin kind {kind}")
    src = src.resolve()
    if not src.is_file():
        raise FileNotFoundError(str(src))
    dest_dir = edit_dir / "bin" / kind
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    if dest.resolve() != src:
        shutil.copy2(src, dest)
    item = {
        "kind": kind,
        "file": str(dest),
        "label": src.name,
        "duration": round(probe_duration(dest), 3),
    }
    items = [i for i in load_bin(edit_dir) if i.get("file") != item["file"]]
    items.append(item)
    save_bin(edit_dir, items)
    return item


def remove_item(edit_dir: Path, file_path: str) -> list[dict]:
    items = [i for i in load_bin(edit_dir) if i.get("file") != file_path]
    save_bin(edit_dir, items)
    return items
