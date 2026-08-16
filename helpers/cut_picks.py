"""Claude-owned cinematic cuts: zoom, drop, and style variations."""

from __future__ import annotations

from pathlib import Path

VARIATIONS = {
    "energy": (
        "Reel energy, not a music video. 2-3 punch-ins only, zoom 1.12-1.28. "
        "Drop empty bridges (I'm hoping, and there are). "
        "4-6 short Mixkit hits with space between them. "
        "B-roll covers the picture for 1.4-2.0s over the line — keep the voice."
    ),
    "tight": (
        "Keep only the strongest sentences. Medium punch-ins (1.15–1.28). "
        "Lean Mixkit. Shorter finished cut."
    ),
    "calm": (
        "Keep all usable speech. Rare zoom, never above 1.12. Sparse Mixkit. "
        "Let the speaker breathe."
    ),
}

MIN_ZOOM = 1.0
MAX_ZOOM = 1.28


def normalize_variation(name: str | None) -> str:
    key = (name or "").strip().lower()
    return key if key in VARIATIONS else "energy"


def apply_cut_picks(ranges: list[dict], cuts: list[dict]) -> list[dict]:
    by_i = {}
    for row in cuts:
        if not isinstance(row, dict):
            continue
        try:
            idx = int(row.get("i"))
        except (TypeError, ValueError):
            continue
        by_i[idx] = row
    out: list[dict] = []
    for idx, raw in enumerate(ranges):
        spec = by_i.get(idx, {})
        if spec.get("keep") is False:
            continue
        item = dict(raw)
        try:
            zoom = float(spec["zoom"]) if spec.get("zoom") is not None else float(item.get("zoom") or 1.0)
        except (TypeError, ValueError):
            zoom = 1.0
        zoom = min(MAX_ZOOM, max(MIN_ZOOM, zoom))
        if zoom > 1.01:
            item["zoom"] = round(zoom, 3)
            reason = str(spec.get("reason") or "").strip()
            if reason:
                item["reason"] = ((item.get("reason") or "") + f" {reason}").strip()
        elif "zoom" in item:
            item.pop("zoom", None)
        out.append(item)
    return out or list(ranges)


def strip_cinematic(ranges: list[dict]) -> list[dict]:
    out = []
    for row in ranges:
        item = dict(row)
        item.pop("zoom", None)
        reason = item.get("reason") or ""
        item["reason"] = reason.replace("Punch-in cut.", "").strip()
        out.append(item)
    return out


def parse_claude_score(data: object) -> dict:
    if not isinstance(data, dict):
        return {"variation": "energy", "cuts": [], "picks": [], "visuals": [], "titles": {}}
    variation = normalize_variation(str(data.get("variation") or "energy"))
    cuts = data.get("cuts") if isinstance(data.get("cuts"), list) else []
    picks = data.get("picks") if isinstance(data.get("picks"), list) else []
    visuals = data.get("visuals") if isinstance(data.get("visuals"), list) else []
    cleaned_cuts = []
    for row in cuts:
        if not isinstance(row, dict):
            continue
        try:
            idx = int(row.get("i"))
        except (TypeError, ValueError):
            continue
        try:
            zoom = float(row["zoom"]) if row.get("zoom") is not None else 1.0
        except (TypeError, ValueError):
            zoom = 1.0
        cleaned_cuts.append({
            "i": idx,
            "keep": row.get("keep") is not False,
            "zoom": min(MAX_ZOOM, max(MIN_ZOOM, zoom)),
            "reason": str(row.get("reason") or "")[:160],
        })
    titles = data.get("titles") if isinstance(data.get("titles"), dict) else {}
    return {"variation": variation, "cuts": cleaned_cuts, "picks": picks, "visuals": visuals, "titles": titles}


def write_cut_brief(*, edit_dir: Path, ranges: list[dict], variation: str) -> Path:
    variation = normalize_variation(variation)
    lines = [
        f"# Cut candidates (variation: {variation})",
        "",
        VARIATIONS[variation],
        "",
        "Index `i` is required. keep=false drops the line. zoom 1.0–1.28.",
        "",
    ]
    for i, row in enumerate(ranges):
        quote = (row.get("quote") or "").replace("\n", " ")
        span = float(row.get("end") or 0) - float(row.get("start") or 0)
        lines.append(
            f"- i={i}  {row.get('beat') or ''}  src {row.get('start'):.2f}-{row.get('end'):.2f} "
            f"({span:.2f}s)  {quote}"
        )
    path = edit_dir / "cut_brief.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def score_prompt(variation: str) -> str:
    variation = normalize_variation(variation)
    style = VARIATIONS[variation]
    return f"""You are the editor AND sound designer for this talking-head cut.
Variation: {variation}
{style}

Read edit/takes_packed.md, edit/cut_brief.md, edit/library_voices.md, and edit/library_visuals.md.

Write ONLY edit/claude_score.json:
{{
  "variation": "{variation}",
  "cuts": [{{"i": 0, "keep": true, "zoom": 1.2, "reason": "punch on hook"}}],
  "picks": [{{"id": "1143", "start_s": 0.05, "duration_s": 1.2, "reason": "whoosh on open"}}],
  "visuals": [
    {{"kind": "broll", "photo_id": "1181675", "query": "laptop coding", "after_i": 1, "duration_s": 2.0, "reason": "shows the work"}},
    {{"kind": "graphic", "text": "CAPTIONS", "start_s": 5.5, "duration_s": 1.6, "reason": "keyword pop"}}
  ],
  "titles": {{
    "hook": "EDIT VIDEO WITH AI",
    "name": null,
    "role": null,
    "keywords": [{{"text": "CAPTIONS", "start_s": 3.5}}, {{"text": "B-ROLL", "start_s": 6.2}}],
    "end": "VIDEO USE"
  }}
}}

Cuts:
- One entry per candidate you care about. keep=false drops that line.
- zoom 1.0 (no punch) to 1.28 (tight). Punch 2-3 meaning beats, not every line.
- Drop empty bridges (I'm hoping, and there are, um).
- i MUST match cut_brief.md.

Audio:
- 4 to 6 Mixkit files on the FINISHED timeline (after your keep/drop).
- Space hits at least 1.8s apart. Do not stack whooshes on the same frame.
- start_s is time in the finished cut, not the raw take. duration_s 0.28-1.2.

Visuals (Caption-style B-roll + graphics):
- 2 to 4 items. Prefer Pexels stills from library_visuals.md (photo_id), plus keyword graphics.
- photo_id MUST be from library_visuals.md when it fits. query is the fallback search.
- B-roll is a FULL-FRAME picture overlay. The talking-head VOICE STAYS. Do not replace the line.
- broll.after_i is the cut index the overlay COVERS (start of that spoken line).
- graphic.text is a short on-screen word (max 18 chars). Do not repeat the hook card.
- Do not invent brands. Tie every visual to a spoken line.

Titles (on-screen copy — be tasteful, Caption-style):
- hook: 2-5 words from the idea of the take. NEVER "talking head", "watch this", or the first seven words dumped in caps.
- name/role: only if the speaker introduces themselves. Otherwise null. Never invent "talking head" as a job title.
- keywords: 1-3 short punches timed to the finished cut.
- end: a short closer or empty. Never "FOLLOW FOR MORE" unless they actually say follow/subscribe.

Do not write edl.json. Do not render. Stop after claude_score.json.
"""
