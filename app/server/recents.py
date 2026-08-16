from __future__ import annotations

import json
from pathlib import Path

from app.server.paths import APP_HOME

RECENTS_PATH = APP_HOME / "recents.json"
MAX_RECENTS = 10


def load_recents() -> list[str]:
    if not RECENTS_PATH.exists():
        return []
    data = json.loads(RECENTS_PATH.read_text(encoding="utf-8"))
    return [str(p) for p in data] if isinstance(data, list) else []


def add_recent(folder: Path) -> list[str]:
    resolved = str(folder.resolve())
    items = [resolved, *[p for p in load_recents() if p != resolved]]
    items = items[:MAX_RECENTS]
    RECENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RECENTS_PATH.write_text(json.dumps(items, indent=2), encoding="utf-8")
    return items
