"""Build a talking-head EDL: tight cuts, captions, graphics overlays.

Does not call Claude. Reads Scribe JSON + source videos, writes edit/edl.json
and animation clips under edit/animations/.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from pack_transcripts import pack_one_file

FILLERS = {
    "um", "uh", "umm", "uhh", "uhhh", "erm", "ah", "ahh",
    "like", "basically", "literally", "actually",
}

WEAK_PHRASES = {"so yeah", "so yeah.", "yeah", "yeah.", "you know", "you know."}

PAD_BEFORE = 0.05
PAD_AFTER = 0.08


def load_takes(edit_dir: Path, folder: Path) -> list[dict]:
    videos = {}
    for p in folder.iterdir():
        if p.is_file() and p.suffix.lower() in {".mp4", ".mov", ".mkv", ".m4v", ".webm", ".avi"}:
            videos[p.stem] = p

    takes = []
    tdir = edit_dir / "transcripts"
    for jp in sorted(tdir.glob("*.json")):
        name, _dur, phrases = pack_one_file(jp, 0.40)
        src = videos.get(name)
        if src is None:
            continue
        takes.append({"name": name, "path": src, "phrases": phrases})
    return takes


def _clean_words(text: str) -> list[str]:
    return [re.sub(r"[^\w']+", "", w).lower() for w in text.split() if w.strip()]


def is_keeper(phrase: dict) -> bool:
    text = (phrase.get("text") or "").strip()
    if not text:
        return False
    if text.lower() in WEAK_PHRASES:
        return False
    words = [w for w in _clean_words(text) if w]
    if not words:
        return False
    if all(w in FILLERS for w in words):
        return False
    return True


def guess_name(phrases: list[dict]) -> str:
    blob = " ".join(p.get("text") or "" for p in phrases)
    m = re.search(r"\bI(?:'m| am)\s+([A-Z][a-zA-Z]+)", blob)
    if m:
        return m.group(1)
    return "SPEAKER"


def hook_line(phrases: list[dict]) -> str:
    for p in phrases:
        if is_keeper(p):
            words = (p.get("text") or "").split()
            return " ".join(words[:7]).upper()
    return "WATCH THIS"


def keyword_lines(phrases: list[dict], limit: int = 2) -> list[tuple[float, str]]:
    seen: set[str] = set()
    out: list[tuple[float, str]] = []
    for p in phrases:
        if not is_keeper(p):
            continue
        for w in re.findall(r"[A-Za-z][A-Za-z0-9]{4,}", p.get("text") or ""):
            key = w.lower()
            if key in FILLERS or key in seen:
                continue
            if key in {"this", "that", "video", "making", "looking", "using", "should"}:
                continue
            seen.add(key)
            out.append((float(p["start"]), w.upper()))
            if len(out) >= limit:
                return out
    return out


def build_ranges(takes: list[dict]) -> list[dict]:
    ranges = []
    beat_i = 0
    for take in takes:
        keepers = [p for p in take["phrases"] if is_keeper(p)]
        for p in keepers:
            start = max(0.0, float(p["start"]) - PAD_BEFORE)
            end = float(p["end"]) + PAD_AFTER
            if end <= start:
                continue
            beat_i += 1
            ranges.append({
                "source": take["name"],
                "start": round(start, 3),
                "end": round(end, 3),
                "beat": "HOOK" if beat_i == 1 else f"TALK_{beat_i:02d}",
                "quote": (p.get("text") or "")[:140],
                "reason": "Tight talking-head keep; silence/fillers dropped.",
            })
    return ranges


def build_talking_head_edl(*, folder: Path, edit_dir: Path) -> dict:
    takes = load_takes(edit_dir, folder)
    if not takes:
        raise RuntimeError("no transcribed takes in this folder")
    ranges = build_ranges(takes)
    if not ranges:
        raise RuntimeError("no usable speech after dropping fillers")

    phrases = [p for t in takes for p in t["phrases"]]
    name = guess_name(phrases)
    hook = hook_line(phrases)
    keys = keyword_lines(phrases)

    from graphics import build_talking_head_graphics
    overlays = build_talking_head_graphics(
        edit_dir=edit_dir,
        speaker=name,
        hook=hook,
        keywords=keys,
        output_duration=sum(r["end"] - r["start"] for r in ranges),
    )

    sources = {t["name"]: str(t["path"].resolve()) for t in takes}
    total = round(sum(r["end"] - r["start"] for r in ranges), 3)
    return {
        "version": 1,
        "sources": sources,
        "ranges": ranges,
        "grade": "cinematic",
        "overlays": overlays,
        "subtitles": "edit/master.srt",
        "total_duration_s": total,
    }
