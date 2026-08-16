"""Claude-chosen B-roll (Mixkit) and keyword graphics for Caption-style cuts."""

from __future__ import annotations

import re
import urllib.parse
import urllib.request
from pathlib import Path

from hidden_proc import run as hidden_run

UA = "video-use-library/1.0 (local editor; +https://mixkit.co/license/)"
ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "library" / "broll"

QUERY_ALIASES = {
    "edit": "technology",
    "editing": "technology",
    "video": "technology",
    "repository": "technology",
    "code": "technology",
    "coding": "technology",
    "software": "technology",
    "system": "technology",
    "laptop": "laptop",
    "computer": "laptop",
    "talk": "people",
    "talking": "people",
    "head": "people",
    "person": "people",
    "trial": "abstract",
    "experience": "people",
    "good": "abstract",
}

MAX_VISUALS = 4
MAX_BROLL = 2.6
MIN_BROLL = 1.2


def slug_query(query: str) -> str:
    words = re.findall(r"[a-zA-Z]{3,}", query or "")
    if not words:
        return "abstract"
    first = words[0].lower()
    return QUERY_ALIASES.get(first, first)


def mixkit_mp4_url(video_id: str, quality: str = "720") -> str:
    return f"https://assets.mixkit.co/videos/{video_id}/{video_id}-{quality}.mp4"


def parse_visuals(data: object) -> list[dict]:
    if isinstance(data, dict):
        raw = data.get("visuals")
    elif isinstance(data, list):
        raw = data
    else:
        raw = None
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        kind = str(row.get("kind") or "").lower()
        if kind == "broll":
            query = str(row.get("query") or row.get("text") or "").strip()
            if not query and not row.get("file") and not row.get("photo_id"):
                continue
            try:
                after = int(row.get("after_i") if row.get("after_i") is not None else 0)
            except (TypeError, ValueError):
                after = 0
            try:
                dur = float(row.get("duration_s") or 2.0)
            except (TypeError, ValueError):
                dur = 2.0
            out.append({
                "kind": "broll",
                "query": query,
                "photo_id": str(row.get("photo_id") or "").strip(),
                "after_i": max(0, after),
                "duration_s": min(MAX_BROLL, max(MIN_BROLL, dur)),
                "file": str(row.get("file") or ""),
                "reason": str(row.get("reason") or "")[:160],
            })
        elif kind == "graphic":
            text = str(row.get("text") or row.get("query") or "").strip()
            if not text:
                continue
            try:
                start = float(row.get("start_s") or 0.4)
                dur = float(row.get("duration_s") or 2.0)
            except (TypeError, ValueError):
                start, dur = 0.4, 2.0
            out.append({
                "kind": "graphic",
                "text": text[:24].upper(),
                "start_s": max(0.0, start),
                "duration_s": min(2.8, max(1.2, dur)),
                "reason": str(row.get("reason") or "")[:160],
            })
        if len(out) >= MAX_VISUALS:
            break
    return out


def _fetch(url: str, dest: Path) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=40) as resp:
            data = resp.read()
        if len(data) < 8000:
            return False
        dest.write_bytes(data)
        return dest.is_file()
    except Exception:
        return False


def _scrape_video_ids(html: str) -> list[str]:
    ids = re.findall(r"assets\.mixkit\.co/videos/(\d+)/", html)
    ids += re.findall(r"/free-stock-video/[a-z0-9-]+-(\d+)/", html)
    seen: list[str] = []
    for sid in ids:
        if sid not in seen:
            seen.append(sid)
    return seen


def search_mixkit_id(query: str) -> str | None:
    slug = slug_query(query)
    pages = [
        f"https://mixkit.co/free-stock-video/{slug}/",
        f"https://mixkit.co/free-stock-video/{urllib.parse.quote(query.replace(' ', '-'))}/",
    ]
    for page in pages:
        try:
            req = urllib.request.Request(page, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=25) as resp:
                html = resp.read().decode("utf-8", "replace")
        except Exception:
            continue
        ids = _scrape_video_ids(html)
        if ids:
            return ids[0]
    return None


def fetch_mixkit_broll(query: str, dest_dir: Path) -> Path | None:
    CACHE.mkdir(parents=True, exist_ok=True)
    dest_dir.mkdir(parents=True, exist_ok=True)
    sid = search_mixkit_id(query)
    if not sid:
        return None
    cached = CACHE / f"mixkit-{sid}.mp4"
    if not cached.is_file():
        ok = _fetch(mixkit_mp4_url(sid, "360"), cached) or _fetch(mixkit_mp4_url(sid, "720"), cached)
        if not ok:
            return None
    dest = dest_dir / cached.name
    if dest.resolve() != cached.resolve():
        dest.write_bytes(cached.read_bytes())
    return dest if dest.is_file() else cached


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def photo_to_clip(photo: Path, dest: Path, duration: float) -> Path:
    """Ken Burns a still into a vertical talking-head cutaway."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    frames = max(30, int(float(duration) * 24))
    vf = (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,"
        f"zoompan=z='min(zoom+0.0009,1.08)':d={frames}:s=1080x1920:fps=24"
    )
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", str(photo),
        "-t", f"{float(duration):.2f}",
        "-vf", vf,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "24",
        "-an", str(dest),
    ]
    try:
        hidden_run(cmd, check=True, capture_output=True)
    except Exception:
        hidden_run(
            [
                "ffmpeg", "-y", "-loop", "1", "-i", str(photo),
                "-t", f"{float(duration):.2f}",
                "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "24",
                "-an", str(dest),
            ],
            check=True,
            capture_output=True,
        )
    return dest


def resolve_broll_file(vis: dict, dest_dir: Path) -> Path | None:
    """Pexels catalog / API first, Mixkit video second."""
    from pexels_library import (
        catalog_by_id,
        load_photo_catalog,
        match_photo,
        pexels_jpeg_url,
        search_pexels_api,
    )

    dest_dir.mkdir(parents=True, exist_ok=True)
    raw = Path(str(vis.get("file") or ""))
    if raw.is_file():
        return raw
    photos = load_photo_catalog().get("items") or []
    by_id = catalog_by_id(photos)
    photo_id = str(vis.get("photo_id") or "").strip()
    item = by_id.get(photo_id) if photo_id else None
    if item is None:
        item = match_photo(str(vis.get("query") or ""), photos)
    if item and Path(item["file"]).is_file():
        return Path(item["file"])
    if photo_id:
        dest = CACHE.parent / "photos" / f"pexels-{photo_id}.jpg"
        if _fetch(pexels_jpeg_url(photo_id), dest):
            return dest
    query = str(vis.get("query") or "workspace")
    api_hit = search_pexels_api(query)
    if api_hit and api_hit.get("url"):
        dest = CACHE.parent / "photos" / f"pexels-{api_hit['id']}.jpg"
        if _fetch(str(api_hit["url"]), dest):
            return dest
    return fetch_mixkit_broll(query, dest_dir)


def make_keyword_graphic(text: str, edit_dir: Path, duration: float) -> Path:
    from graphics import _draw_keyword, _save_clip
    slot = edit_dir / "animations" / "talking_head"
    slot.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^\w]+", "_", text.lower())[:24] or "key"
    png = slot / f"claude_{safe}.png"
    _draw_keyword(text[:18]).save(png)
    return _save_clip(png, slot / f"claude_{safe}.mov", duration)


def output_time_at(ranges: list[dict], index: int) -> float:
    """Start time of range `index` on the finished timeline."""
    t = 0.0
    idx = max(0, int(index))
    for i, row in enumerate(ranges):
        if i >= idx:
            return round(t, 3)
        t += float(row.get("end") or 0) - float(row.get("start") or 0)
    return round(t, 3)


def drop_duplicate_graphics(
    visuals: list[dict], *, hook: str = "", keywords: list | None = None
) -> list[dict]:
    """Skip Claude graphics that already exist as hook / keyword pills."""
    used = {(hook or "").upper()}
    for key in keywords or []:
        if isinstance(key, (tuple, list)) and len(key) >= 2:
            used.add(str(key[1]).upper())
        elif isinstance(key, str):
            used.add(key.upper())
    out: list[dict] = []
    for vis in visuals:
        if vis.get("kind") == "graphic":
            text = str(vis.get("text") or "").strip().upper()
            if not text:
                continue
            if text in used or any(text in label for label in used if label):
                continue
            used.add(text)
        out.append(vis)
    return out


def apply_visuals(edl: dict, visuals: list[dict], edit_dir: Path, *, fetch: bool = True) -> dict:
    """B-roll covers the picture. Talking-head voice stays on the timeline."""
    ranges = list(edl.get("ranges") or [])
    overlays = list(edl.get("overlays") or [])
    total = float(edl.get("total_duration_s") or 0)
    if total <= 0:
        total = sum(float(r.get("end") or 0) - float(r.get("start") or 0) for r in ranges)
    broll_i = 0
    for vis in visuals:
        kind = vis.get("kind")
        if kind == "broll":
            raw = Path(str(vis.get("file") or ""))
            if not raw.is_file() and fetch:
                got = resolve_broll_file(vis, edit_dir / "bin" / "broll")
                raw = got if got else raw
            if raw.is_file() and raw.suffix.lower() in IMAGE_EXTS:
                clip = edit_dir / "bin" / "broll" / f"{raw.stem}.mp4"
                raw = photo_to_clip(raw, clip, float(vis.get("duration_s") or 2.0))
            try:
                cover_i = int(vis.get("after_i") or 0)
            except (TypeError, ValueError):
                cover_i = 0
            start = output_time_at(ranges, cover_i)
            dur = float(vis.get("duration_s") or 2.0)
            if total > 0:
                dur = min(dur, max(0.8, total - start))
            if not raw.is_file():
                text = str(vis.get("query") or "B-ROLL").upper()[:18]
                clip = make_keyword_graphic(text, edit_dir, dur)
                overlays.append({
                    "file": str(clip),
                    "start_in_output": round(start if start > 0.2 else 1.2 + broll_i * 2.4, 2),
                    "duration": dur,
                    "kind": "broll",
                })
                broll_i += 1
                continue
            overlays.append({
                "file": str(raw.resolve()),
                "start_in_output": round(start, 2),
                "duration": dur,
                "kind": "broll",
            })
            broll_i += 1
        elif kind == "graphic":
            clip = make_keyword_graphic(str(vis.get("text") or "NOW"), edit_dir, float(vis.get("duration_s") or 2.0))
            overlays.append({
                "file": str(clip),
                "start_in_output": round(float(vis.get("start_s") or 0.4), 2),
                "duration": float(vis.get("duration_s") or 2.0),
            })
    edl["overlays"] = overlays
    edl["total_duration_s"] = round(total, 3)
    return edl
