"""Claude designs the Mixkit bed: many layered files on one talking-head cut."""

from __future__ import annotations

from pathlib import Path

JUNK_KEYS = (
    "dog", "bark", "alarm", "tick tock", "vacuum", "cricket", "insect",
    "monkey", "ghostly", "insect whoosh",
)

MAX_PICKS = 6
MAX_DURATION = 1.2
MIN_DURATION = 0.28
MIN_GAP = 1.8


def editorial_catalog(items: list[dict]) -> list[dict]:
    """Whole Mixkit library minus obvious junk. Claude chooses what fits."""
    out: list[dict] = []
    for item in items:
        blob = f"{item.get('title') or ''} {' '.join(item.get('tags') or [])}".lower()
        if any(key in blob for key in JUNK_KEYS):
            continue
        if item.get("file"):
            out.append(item)
    return out


def voice_catalog(items: list[dict]) -> list[dict]:
    return editorial_catalog(items)


def catalog_by_id(items: list[dict]) -> dict[str, dict]:
    return {str(item.get("id")): item for item in items if item.get("id") is not None}


def parse_voice_picks(data: object, by_id: dict[str, dict], *, total_s: float) -> list[dict]:
    if isinstance(data, dict):
        raw = data.get("picks")
    elif isinstance(data, list):
        raw = data
    else:
        raw = None
    if not isinstance(raw, list):
        return []
    picks: list[dict] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        item = by_id.get(str(row.get("id") or ""))
        if not item or not item.get("file"):
            continue
        try:
            start = float(row.get("start_s") if row.get("start_s") is not None else row.get("start_in_output") or 0)
            duration = float(row.get("duration_s") if row.get("duration_s") is not None else row.get("duration") or 1.2)
        except (TypeError, ValueError):
            continue
        start = max(0.0, start)
        if total_s > 0:
            start = min(start, max(0.0, total_s - 0.2))
        duration = min(MAX_DURATION, max(MIN_DURATION, duration))
        picks.append({
            "file": str(item["file"]),
            "start_in_output": round(start, 2),
            "duration": round(duration, 3),
            "label": item.get("title") or Path(str(item["file"])).name,
            "id": str(item.get("id")),
            "reason": str(row.get("reason") or "")[:160],
        })
        if len(picks) >= MAX_PICKS:
            break
    return space_audio_picks(picks, total_s=total_s)


def space_audio_picks(
    picks: list[dict], *, total_s: float, min_gap: float = MIN_GAP
) -> list[dict]:
    """Keep Mixkit hits from stacking into one muddy bed."""
    if not picks:
        return []
    ordered = sorted(picks, key=lambda p: float(p.get("start_in_output") or 0))
    out: list[dict] = []
    last_start = -min_gap
    for raw in ordered:
        item = dict(raw)
        start = float(item.get("start_in_output") or 0)
        if start < last_start + min_gap:
            start = last_start + min_gap
        if total_s > 0 and start > max(0.0, total_s - 0.25):
            continue
        item["start_in_output"] = round(max(0.0, start), 2)
        out.append(item)
        last_start = float(item["start_in_output"])
    return out


def apply_voice_picks(edl: dict, overlays: list[dict], *, replace: bool = False) -> dict:
    if replace:
        edl["audio_overlays"] = list(overlays)
    else:
        audio = list(edl.get("audio_overlays") or [])
        audio.extend(overlays)
        edl["audio_overlays"] = audio
    return edl


def write_voice_brief(*, edit_dir: Path, edl: dict, voices: list[dict]) -> Path:
    lines = [
        "# Mixkit library Claude may score onto this cut",
        "",
        f"Finished cut length: {float(edl.get('total_duration_s') or 0):.2f}s",
        "",
        "## Timeline (times are in the FINISHED cut)",
    ]
    t = 0.0
    for row in edl.get("ranges") or []:
        span = float(row.get("end") or 0) - float(row.get("start") or 0)
        quote = (row.get("quote") or "").replace("\n", " ")
        zoom = row.get("zoom")
        punch = f"  punch-in {zoom}" if zoom else ""
        lines.append(f"- {t:.2f}-{t + span:.2f}s  {row.get('beat') or ''}{punch}  {quote}")
        t += span
    lines.extend(["", "## Catalog (use these ids only)", ""])
    for item in voices:
        lines.append(f"- id={item.get('id')}  {item.get('title')}")
    path = edit_dir / "library_voices.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


VOICE_PROMPT = """You are the sound designer for this talking-head edit.

Read edit/takes_packed.md and edit/library_voices.md.

Write ONLY edit/voice_picks.json:
{"picks":[{"id":"1143","start_s":0.05,"duration_s":1.2,"reason":"whoosh on hook"}]}

Design a lean Mixkit bed on ONE video:
- 4 to 6 picks. Space them at least 1.8s apart. Do not stack whooshes.
- Cover the open (whoosh), one or two punch-ins (hits), and the end (riser/button).
- start_s is time in the FINISHED cut (Timeline section), not the raw take.
- duration_s between 0.28 and 1.2. Short hits beat long beds.
- Every id MUST be in the catalog. Skip animals, alarms, and anything that fights speech.
- Do not write edl.json. Do not render. Stop after voice_picks.json.
"""
