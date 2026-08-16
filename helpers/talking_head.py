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
            if p.name.endswith("-EDIT.mp4") or p.name in {"preview.mp4", "final.mp4"}:
                continue
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
    from media_bin import load_bin
    overlays = build_talking_head_graphics(
        edit_dir=edit_dir,
        speaker=name,
        hook=hook,
        keywords=keys,
        output_duration=sum(r["end"] - r["start"] for r in ranges),
    )
    sources = {t["name"]: str(t["path"].resolve()) for t in takes}
    extras = load_bin(edit_dir)
    ranges, overlays, sources = apply_bin(ranges, overlays, sources, extras, edit_dir)
    total = round(sum(r["end"] - r["start"] for r in ranges), 3)
    return {
        "version": 1,
        "sources": sources,
        "ranges": ranges,
        "grade": "cinematic",
        "overlays": overlays,
        "subtitles": "master.srt",
        "total_duration_s": total,
    }


def apply_bin(
    ranges: list[dict],
    overlays: list[dict],
    sources: dict,
    extras: list[dict],
    edit_dir: Path,
) -> tuple[list[dict], list[dict], dict]:
    """Fold user B-roll into the timeline and graphics/voice onto overlays."""
    from graphics import _save_clip
    from media_bin import AUDIO_EXTS, IMAGE_EXTS

    talk = list(ranges)
    inserted = 0
    t_cursor = 4.5
    for item in extras:
        kind = item.get("kind")
        raw = Path(str(item.get("file") or ""))
        if not raw.is_file():
            continue
        dur = float(item.get("duration") or 2.0)
        if kind == "broll":
            key = f"broll_{raw.stem}"
            sources[key] = str(raw.resolve())
            cut_dur = min(dur, 3.2)
            talk.insert(min(1 + inserted, len(talk)), {
                "source": key,
                "start": 0.0,
                "end": round(cut_dur, 3),
                "beat": "BROLL",
                "quote": item.get("label") or raw.name,
                "reason": "User B-roll cutaway",
            })
            inserted += 1
        elif kind == "graphic":
            clip = raw
            if raw.suffix.lower() in IMAGE_EXTS:
                clip = _save_clip(raw, edit_dir / "bin" / "graphic" / f"{raw.stem}.mov", min(dur, 2.8))
            overlays.append({
                "file": str(clip),
                "start_in_output": round(t_cursor, 2),
                "duration": min(dur, 2.8),
            })
            t_cursor += 3.0
        elif kind == "voice":
            wrapped = _wrap_voice(raw, edit_dir / "bin" / "voice" / f"{raw.stem}.mp4", dur)
            key = f"voice_{raw.stem}"
            sources[key] = str(wrapped.resolve())
            talk.insert(min(1 + inserted, len(talk)), {
                "source": key,
                "start": 0.0,
                "end": round(min(dur, 8.0), 3),
                "beat": "VO",
                "quote": item.get("label") or "voice clip",
                "reason": "User voice / viral hook clip",
            })
            inserted += 1
            _ = AUDIO_EXTS
    return talk, overlays, sources


def _wrap_voice(src: Path, dest: Path, duration: float) -> Path:
    import subprocess
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.suffix.lower() in {".mp4", ".mov", ".webm", ".mkv", ".m4v"}:
        return src
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=0x111111:s=1080x1920:d={max(duration, 0.8):.2f}",
        "-i", str(src),
        "-shortest",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        str(dest),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return dest

