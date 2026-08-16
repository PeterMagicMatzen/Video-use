"""Read the on-disk Mixkit SFX catalog."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "library" / "sfx" / "catalog.json"


def load_catalog() -> dict:
    if not CATALOG.is_file():
        return {"count": 0, "items": [], "source": "https://mixkit.co/free-sound-effects/"}
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    items = []
    for item in data.get("items") or []:
        path = Path(item.get("file") or "")
        if not path.is_file():
            rel = item.get("rel")
            if rel:
                path = ROOT / rel
        if not path.is_file():
            continue
        row = dict(item)
        row["file"] = str(path)
        items.append(row)
    data["items"] = items
    data["count"] = len(items)
    return data
