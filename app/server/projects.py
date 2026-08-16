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
    return dest_dir
