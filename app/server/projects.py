"""Give each picked talking-head clip its own project folder."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from app.server.paths import APP_HOME

SKIP_VIDEO_NAMES = {
    "preview.mp4", "final.mp4", "base.mp4", "base_preview.mp4",
    "base_draft.mp4",
}


def is_edit_artifact(path: Path) -> bool:
    name = path.name
    if name in SKIP_VIDEO_NAMES:
        return True
    if name.endswith("-EDIT.mp4"):
        return True
    return False


def isolate_clip(video: Path) -> Path:
    """Copy/link a single clip into ~/.video-use/projects/<stem>/ so Desktop is not the project."""
    video = video.resolve()
    safe = re.sub(r"[^\w]+", "-", video.stem).strip("-")[:72] or "clip"
    dest_dir = APP_HOME / "projects" / safe
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / video.name
    if not dest.exists():
        try:
            dest.hardlink_to(video)
        except OSError:
            shutil.copy2(video, dest)
    _import_sibling_edit(video, dest_dir)
    return dest_dir


def _import_sibling_edit(video: Path, dest_dir: Path) -> None:
    """Reuse a transcript only when it is for THIS filename."""
    dest_edit = dest_dir / "edit"
    dest_json = dest_edit / "transcripts" / f"{video.stem}.json"
    if dest_json.is_file():
        return
    src_json = video.parent / "edit" / "transcripts" / f"{video.stem}.json"
    if not src_json.is_file():
        return
    dest_json.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_json, dest_json)
