"""Read the on-disk Mixkit SFX catalog."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "library" / "sfx" / "catalog.json"


SFX_ROLES = {
    "whoosh": ("whoosh", "swoosh", "sweep"),
    "hit": ("hit", "impact", "blow"),
    "riser": ("riser",),
}


def pick_auto_sfx(items: list[dict] | None = None) -> list[dict]:
    """Pick one Mixkit whoosh, hit, and riser. No user click required."""
    if items is None:
        items = load_catalog().get("items") or []
    picked: list[dict] = []
    used: set[str] = set()
    for role, keys in SFX_ROLES.items():
        for item in items:
            path = str(item.get("file") or "")
            if not path or path in used:
                continue
            blob = f"{item.get('title') or ''} {' '.join(item.get('tags') or [])}".lower()
            if not any(key in blob for key in keys):
                continue
            used.add(path)
            dest = Path(path)
            duration = 1.2
            if dest.is_file():
                from media_bin import probe_duration
                duration = probe_duration(dest)
            picked.append({
                "kind": "sfx",
                "role": role,
                "file": path,
                "label": item.get("title") or dest.name,
                "duration": round(float(duration), 3),
            })
            break
    return picked


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
