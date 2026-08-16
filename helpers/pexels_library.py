"""Local Pexels stills Claude can pick, plus optional live API search."""

from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PHOTO_DIR = ROOT / "library" / "photos"
CATALOG = PHOTO_DIR / "catalog.json"
UA = "video-use-library/1.0 (local editor; +https://www.pexels.com/license/)"


def load_env_key() -> str:
    repo_env = ROOT / ".env"
    for candidate in (repo_env, Path(".env")):
        if not candidate.exists():
            continue
        for line in candidate.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == "PEXELS_API_KEY":
                return value.strip().strip('"').strip("'")
    return os.environ.get("PEXELS_API_KEY", "")


def load_photo_catalog() -> dict:
    if not CATALOG.is_file():
        return {"count": 0, "items": [], "source": "https://www.pexels.com/"}
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


def catalog_by_id(items: list[dict] | None = None) -> dict[str, dict]:
    if items is None:
        items = load_photo_catalog().get("items") or []
    return {str(item.get("id")): item for item in items if item.get("id") is not None}


def match_photo(query: str, items: list[dict] | None = None) -> dict | None:
    if items is None:
        items = load_photo_catalog().get("items") or []
    words = [w.lower() for w in re.findall(r"[a-zA-Z]{3,}", query or "")]
    if not words:
        return items[0] if items else None
    best = None
    best_score = 0
    for item in items:
        blob = f"{item.get('title') or ''} {' '.join(item.get('tags') or [])}".lower()
        score = sum(1 for word in words if word in blob)
        if str(item.get("id")) in query:
            score += 3
        if score > best_score:
            best, best_score = item, score
    return best if best_score else None


def pexels_jpeg_url(photo_id: str, width: int = 1280) -> str:
    return (
        f"https://images.pexels.com/photos/{photo_id}/pexels-photo-{photo_id}.jpeg"
        f"?auto=compress&cs=tinysrgb&w={width}"
    )


def search_pexels_api(query: str, api_key: str | None = None) -> dict | None:
    key = api_key if api_key is not None else load_env_key()
    if not key:
        return None
    url = "https://api.pexels.com/v1/search?" + urllib.parse.urlencode({
        "query": query,
        "per_page": 5,
        "orientation": "portrait",
    })
    req = urllib.request.Request(url, headers={"Authorization": key, "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
    except Exception:
        return None
    photos = data.get("photos") or []
    if not photos:
        return None
    photo = photos[0]
    src = (photo.get("src") or {})
    return {
        "id": str(photo.get("id")),
        "title": (photo.get("alt") or query)[:80],
        "url": src.get("large2x") or src.get("large") or src.get("original"),
        "tags": [query],
    }


def write_visual_brief(edit_dir: Path) -> Path:
    items = load_photo_catalog().get("items") or []
    lines = [
        "# Pexels stills Claude may cut in as B-roll",
        "",
        "Prefer photo_id from this list. query is the fallback search.",
        "Pexels License: free commercial use, attribution not required.",
        "",
    ]
    for item in items:
        tags = ", ".join(item.get("tags") or [])
        lines.append(f"- photo_id={item.get('id')}  {item.get('title')}  [{tags}]")
    path = edit_dir / "library_visuals.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
