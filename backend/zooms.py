"""Speech-driven cinematic camera moves + keyword punch-in snaps."""

PUNCH_PUNCT = {"!", "?"}
SNAP_DECAY = 0.38


def _sensitivity_curve(sensitivity: float) -> dict:
    """Map a 0..1 dial into snap tuning. Low = rare & big, high = frequent & subtle."""
    s = max(0.0, min(1.0, sensitivity))
    return {
        "threshold": 1.25 - 0.75 * s,   # higher bar (rarer) at low s
        "min_gap": 2.4 - 1.7 * s,       # more spacing (rarer) at low s
        "max_snaps": round(2 + 7 * s),  # fewer snaps at low s
        "amp_mult": 1.7 - 0.9 * s,      # bigger snaps at low s, subtler at high s
    }

HOOK_WORDS = {
    "never", "always", "everyone", "nobody", "everything", "nothing", "best", "worst",
    "biggest", "fastest", "hardest", "secret", "secrets", "free", "huge", "insane",
    "crazy", "stop", "listen", "watch", "million", "billion", "thousand", "percent",
    "proven", "guarantee", "guaranteed", "instantly", "literally", "actually", "truth",
    "mistake", "mistakes", "hack", "hacks", "rule", "rules", "first", "last", "only",
    "must", "need", "why", "how", "wrong", "right", "now", "today", "forever",
}


def _norm(text: str) -> str:
    return "".join(c for c in (text or "").lower() if c.isalpha())


def _pace(items: list) -> float:
    """Median seconds-per-character, so emphasis is judged against this speaker's own rate."""
    rates = []
    for w in items:
        norm = _norm(w.get("text"))
        if len(norm) >= 3:
            rates.append((w["end"] - w["start"]) / len(norm))
    if not rates:
        return 0.09
    rates.sort()
    return max(0.03, rates[len(rates) // 2])


def _emphasis_score(word: dict, next_gap: float, pace: float = 0.09) -> float:
    raw = (word.get("text") or "").strip()
    norm = _norm(raw)
    if not norm:
        return 0.0
    dur = max(0.01, word["end"] - word["start"])
    score = 0.0
    if raw[-1:] in PUNCH_PUNCT:
        score += 1.3
    if len(norm) >= 3:
        ratio = (dur / len(norm)) / pace
        if ratio > 1.8:
            score += 1.3
        elif ratio > 1.3:
            score += 0.9
    if next_gap > 0.5:
        score += 0.5
    elif next_gap > 0.18:
        score += 0.35
    if norm in HOOK_WORDS:
        score += 1.4
    if any(c.isdigit() for c in raw):
        score += 0.5
    if len(norm) >= 8:
        score += 0.3
    return score


def _snaps(in_range: list, seg_start: float, seg_end: float,
           base_top: float, intensity: float, pace: float, tune: dict) -> list:
    scored = []
    for i, w in enumerate(in_range):
        nxt = in_range[i + 1]["start"] if i + 1 < len(in_range) else seg_end
        score = _emphasis_score(w, max(0.0, nxt - w["end"]), pace)
        if score >= tune["threshold"]:
            scored.append((score, w))
    scored.sort(key=lambda s: -s[0])

    picked = []
    for score, w in scored:
        t = max(0.0, w["start"] - seg_start)
        if t > (seg_end - seg_start) - 0.12:
            continue
        if any(abs(t - p["t"]) < tune["min_gap"] for p in picked):
            continue
        amp = (0.07 + 0.07 * min(1.0, score / 2.4)) * max(0.2, min(1.6, intensity)) * tune["amp_mult"]
        amp = min(amp, max(0.02, 1.32 - base_top))
        picked.append({
            "t": round(t, 3),
            "amp": round(amp, 4),
            "decay": SNAP_DECAY,
            "word": (w.get("text") or "").strip(),
            "score": round(score, 2),
        })
        if len(picked) >= tune["max_snaps"]:
            break
    picked.sort(key=lambda p: p["t"])
    return picked


def plan(words: list, ranges: list, intensity: float = 1.0, punch_ins: bool = True,
         punch_sensitivity: float = 0.5) -> list:
    items = [w for w in words if w.get("type") == "word" and w.get("start") is not None]
    pace = _pace(items)
    tune = _sensitivity_curve(punch_sensitivity)
    moves = []
    for i, (a, b) in enumerate(ranges):
        dur = max(0.1, b - a)
        in_range = [w for w in items if w["end"] > a and w["start"] < b]
        wps = len(in_range) / dur
        emphatic = any((w.get("text") or "").strip()[-1:] in PUNCH_PUNCT for w in in_range)
        energy = min(1.0, wps / 4.0)
        amp = (0.045 + 0.075 * energy) * max(0.2, min(1.6, intensity))

        if dur < 1.0:
            kind, z0, z1 = "punch", 1.0 + amp, 1.0 + amp
        elif emphatic:
            kind, z0, z1 = "punch in", 1.0 + amp * 0.3, 1.0 + amp * 1.4
        elif i % 3 == 2:
            kind, z0, z1 = "hold", 1.0, 1.0
        elif i % 2 == 0:
            kind, z0, z1 = "push in", 1.0, 1.0 + amp
        else:
            kind, z0, z1 = "pull out", 1.0 + amp, 1.0

        snaps = _snaps(in_range, a, b, max(z0, z1), intensity, pace, tune) if punch_ins else []
        moves.append({
            "index": i,
            "kind": kind,
            "z0": round(z0, 3),
            "z1": round(z1, 3),
            "start": round(a, 3),
            "end": round(b, 3),
            "words": len(in_range),
            "wps": round(wps, 2),
            "snaps": snaps,
        })
    return moves
