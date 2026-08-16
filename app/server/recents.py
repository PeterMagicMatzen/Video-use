from __future__ import annotations

import json
from pathlib import Path

from app.server.paths import APP_HOME

RECENTS_PATH = APP_HOME / "recents.json"
MAX_RECENTS = 10
SKIP_RECENT_NAMES = {"desktop", "downloads", "documents", "pictures", "videos", "music"}


def load_recents() -> list[str]:
    if not RECENTS_PATH.exists():
        return []
    data = json.loads(RECENTS_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        return []
    items = []
    for item in data:
        path = Path(str(item))
        if path.name.lower() in SKIP_RECENT_NAMES:
            continue
        items.append(str(item))
    return items


def clear_recents() -> None:
    if RECENTS_PATH.exists():
        RECENTS_PATH.write_text("[]", encoding="utf-8")


def add_recent(folder: Path) -> list[str]:
    resolved_path = folder.resolve()
    if resolved_path.name.lower() in SKIP_RECENT_NAMES:
        return load_recents()
    resolved = str(resolved_path)
    items = [resolved, *[p for p in load_recents() if p != resolved]]
    items = items[:MAX_RECENTS]
    RECENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RECENTS_PATH.write_text(json.dumps(items, indent=2), encoding="utf-8")
    return items
