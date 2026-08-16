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

WEAK_PHRASES = {
    "so yeah", "so yeah.", "yeah", "yeah.", "you know", "you know.",
    "i'm hoping", "im hoping", "and there are", "and then", "you know what",
}

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
    normalized = re.sub(r"[.,!?]+$", "", text).strip().lower()
    if normalized in WEAK_PHRASES or text.lower() in WEAK_PHRASES:
        return False
    words = [w for w in _clean_words(text) if w]
    if not words:
        return False
    if all(w in FILLERS for w in words):
        return False
    closers = {"that's it", "thats it", "done", "thanks"}
    meat = {"caption", "captions", "broll", "b-roll", "b-rolls", "graphic", "graphics", "edit", "video", "ai"}
    if len(words) <= 2 and normalized not in closers and not any(w in meat for w in words):
        return False
    if len(words) <= 3 and normalized in {"and there are", "i'm hoping", "and then"}:
        return False
    return True


def guess_name(phrases: list[dict]) -> str | None:
    blob = " ".join(p.get("text") or "" for p in phrases)
    m = re.search(r"\bI(?:'m| am)\s+([A-Z][a-zA-Z]{2,})", blob)
    if m:
        return m.group(1)
    return None


_WEAK_HOOK = (
    "this is", "that is", "so ", "um", "uh", "okay", "ok ", "alright",
    "hi ", "hey ", "hello",
)
_KEYWORD_SKIP = FILLERS | {
    "this", "that", "video", "making", "looking", "using", "should",
    "hoping", "added", "there", "somewhere", "explaining", "sample",
    "second", "first", "really", "going", "about", "from", "here",
    "them", "have", "just", "with", "into", "your", "their",
}


def hook_line(phrases: list[dict]) -> str:
    blob = " ".join(p.get("text") or "" for p in phrases if is_keeper(p))
    low = blob.lower()
    if re.search(r"\bb-?rolls?\b", low) and re.search(r"\bgraphics?\b", low):
        return "B-ROLL + GRAPHICS"
    if re.search(r"\bcaptions?\b", low):
        return "AUTO CAPTIONS"
    if re.search(r"video\s*use", low):
        return "EDIT WITH VIDEO USE"
    if re.search(r"\bedit(?:ing)? videos?\b", low) and re.search(r"\bai\b", low):
        return "EDIT VIDEO WITH AI"
    for p in phrases:
        if not is_keeper(p):
            continue
        text = (p.get("text") or "").strip()
        if any(text.lower().startswith(w) for w in _WEAK_HOOK):
            continue
        words = [w for w in re.findall(r"[A-Za-z0-9']+", text) if w]
        if 2 <= len(words) <= 6:
            return " ".join(words).upper()[:36]
    return ""


def keyword_lines(phrases: list[dict], limit: int = 3) -> list[tuple[float, str]]:
    seen: set[str] = set()
    out: list[tuple[float, str]] = []

    def add(start: float, label: str) -> None:
        key = label.lower()
        if key in seen or len(out) >= limit:
            return
        seen.add(key)
        out.append((start, label))

    for p in phrases:
        if not is_keeper(p):
            continue
        text = p.get("text") or ""
        start = float(p["start"])
        if re.search(r"\bcaptions?\b", text, re.I):
            add(start, "CAPTIONS")
        if re.search(r"\bb-?rolls?\b", text, re.I):
            add(start, "B-ROLL")
            seen.add("rolls")
        if re.search(r"\bgraphics?\b", text, re.I):
            add(start, "GRAPHICS")
        if re.search(r"video\s*use", text, re.I):
            add(start, "VIDEO USE")
    if len(out) >= limit:
        return out[:limit]
    for p in phrases:
        if not is_keeper(p) or len(out) >= limit:
            continue
        start = float(p["start"])
        for w in re.findall(r"[A-Za-z][A-Za-z0-9]{4,}", p.get("text") or ""):
            key = w.lower()
            if key in _KEYWORD_SKIP or key in seen:
                continue
            add(start, w.upper())
            if len(out) >= limit:
                break
    return out[:limit]


_GENERIC_ROLES = {
    "talking head", "talking-head", "speaker", "creator", "youtuber",
    "influencer", "host", "person",
}


def keywords_not_in_hook(hook: str, keys: list[tuple[float, str]]) -> list[tuple[float, str]]:
    """Drop keyword pills that already sit in the hook card (B-ROLL + GRAPHICS)."""
    hook_u = (hook or "").upper()
    out: list[tuple[float, str]] = []
    for start, label in keys:
        lab = (label or "").strip().upper()
        if not lab:
            continue
        if hook_u and lab in hook_u:
            continue
        out.append((start, label))
    return out


def title_pack(phrases: list[dict]) -> dict:
    name = guess_name(phrases)
    hook = hook_line(phrases)
    keys = keywords_not_in_hook(hook, keyword_lines(phrases, limit=6))[:3]
    blob = " ".join(p.get("text") or "" for p in phrases)
    end = "VIDEO USE" if re.search(r"video\s*use", blob, re.I) else ""
    return {
        "name": name,
        "role": None,
        "hook": hook,
        "keywords": keys,
        "end": end,
    }


def apply_claude_titles(pack: dict, titles: object) -> dict:
    out = dict(pack)
    if not isinstance(titles, dict):
        return out
    hook = str(titles.get("hook") or "").strip()
    if hook and hook.upper() not in {"WATCH THIS", "TALKING HEAD"}:
        out["hook"] = hook[:42]
    name = str(titles.get("name") or "").strip()
    if name and name.upper() not in {"SPEAKER", "HOST"}:
        out["name"] = name
    role = str(titles.get("role") or "").strip()
    if role and role.lower() not in _GENERIC_ROLES:
        out["role"] = role
    else:
        out["role"] = None
    raw_keys = titles.get("keywords")
    if isinstance(raw_keys, list) and raw_keys:
        cleaned = []
        for row in raw_keys[:3]:
            if isinstance(row, dict):
                text = str(row.get("text") or "").strip()
                try:
                    start = float(row.get("start_s") or 0)
                except (TypeError, ValueError):
                    start = 0.0
            else:
                text = str(row).strip()
                start = 0.0
            if text and text.upper() not in {"TALKING HEAD", "SPEAKER"}:
                cleaned.append((start, text.upper()[:18]))
        if cleaned:
            out["keywords"] = cleaned
    end = str(titles.get("end") or "").strip()
    if end.upper() in {"FOLLOW FOR MORE", "FOLLOW", "SUBSCRIBE"}:
        out["end"] = ""
    elif end:
        out["end"] = end[:28]
    return out


def mark_cinematic_cuts(ranges: list[dict]) -> list[dict]:
    """Punch-in on the hook and every other talk beat (same footage, tighter frame)."""
    out: list[dict] = []
    talk_i = 0
    for row in ranges:
        item = dict(row)
        beat = str(item.get("beat") or "")
        if beat == "HOOK":
            item["zoom"] = 1.12
        elif beat.startswith("TALK"):
            span = float(item.get("end") or 0) - float(item.get("start") or 0)
            if span >= 1.0:
                talk_i += 1
                if talk_i % 2 == 1:
                    item["zoom"] = 1.28
                    item["reason"] = ((item.get("reason") or "") + " Punch-in cut.").strip()
        out.append(item)
    return out


def merge_auto_sfx(user: list[dict], auto: list[dict]) -> list[dict]:
    """If the user already picked SFX, keep those. Otherwise attach the Mixkit package."""
    if any(item.get("kind") == "sfx" for item in user):
        return list(user)
    return list(user) + list(auto)


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


def build_talking_head_edl(*, folder: Path, edit_dir: Path, auto_zoom: bool = False) -> dict:
    takes = load_takes(edit_dir, folder)
    if not takes:
        raise RuntimeError("no transcribed takes in this folder")
    ranges = build_ranges(takes)
    if auto_zoom:
        ranges = mark_cinematic_cuts(ranges)
    if not ranges:
        raise RuntimeError("no usable speech after dropping fillers")

    phrases = [p for t in takes for p in t["phrases"]]
    pack = title_pack(phrases)
    total = sum(r["end"] - r["start"] for r in ranges)

    from graphics import build_talking_head_graphics
    from media_bin import load_bin
    overlays = build_talking_head_graphics(
        edit_dir=edit_dir,
        speaker=pack.get("name"),
        role=pack.get("role"),
        hook=pack.get("hook") or "",
        keywords=pack.get("keywords") or [],
        end=pack.get("end") or "",
        output_duration=total,
    )
    sources = {t["name"]: str(t["path"].resolve()) for t in takes}
    extras = load_bin(edit_dir)
    ranges, overlays, sources, audio_overlays = apply_bin(ranges, overlays, sources, extras, edit_dir)
    total = round(sum(r["end"] - r["start"] for r in ranges), 3)
    return {
        "version": 1,
        "sources": sources,
        "ranges": ranges,
        "grade": "natural",
        "overlays": overlays,
        "audio_overlays": audio_overlays,
        "subtitles": "master.srt",
        "total_duration_s": total,
    }


def apply_bin(
    ranges: list[dict],
    overlays: list[dict],
    sources: dict,
    extras: list[dict],
    edit_dir: Path,
) -> tuple[list[dict], list[dict], dict, list[dict]]:
    """Fold user B-roll into the timeline and graphics/SFX onto the mix."""
    from graphics import _save_clip
    from media_bin import AUDIO_EXTS, IMAGE_EXTS

    talk = list(ranges)
    audio_overlays: list[dict] = []
    inserted = 0
    t_cursor = 0.12
    for item in extras:
        kind = item.get("kind")
        raw = Path(str(item.get("file") or ""))
        if not raw.is_file():
            continue
        dur = float(item.get("duration") or 2.0)
        if kind == "broll":
            clip = raw
            if raw.suffix.lower() in IMAGE_EXTS:
                from visual_picks import photo_to_clip
                clip = photo_to_clip(
                    raw, edit_dir / "bin" / "broll" / f"{raw.stem}.mp4", min(dur, 2.6)
                )
            from visual_picks import output_time_at
            start = output_time_at(talk, 1) if len(talk) > 1 else 0.4
            overlays.append({
                "file": str(clip.resolve()),
                "start_in_output": round(start, 2),
                "duration": min(dur, 2.6),
                "kind": "broll",
            })
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
        elif kind == "sfx" or (kind == "voice" and raw.suffix.lower() in AUDIO_EXTS):
            name = raw.name.lower()
            if item.get("start_in_output") is not None:
                start = float(item["start_in_output"])
            else:
                start = 0.08 if any(k in name for k in ("whoosh", "swoosh", "intro", "impact", "hit")) else t_cursor
            audio_overlays.append({
                "file": str(raw.resolve()),
                "start_in_output": round(start, 2),
                "duration": min(dur, 6.0),
            })
            t_cursor = max(t_cursor, start) + 2.2
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
    return talk, overlays, sources, audio_overlays


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
    from hidden_proc import run as hidden_run
    hidden_run(cmd, check=True, capture_output=True)
    return dest

