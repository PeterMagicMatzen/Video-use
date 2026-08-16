"""Speech-driven cinematic camera moves: each kept speech beat gets a digital zoom."""

PUNCH_PUNCT = {"!", "?"}


def plan(words: list, ranges: list, intensity: float = 1.0) -> list:
    items = [w for w in words if w.get("type") == "word" and w.get("start") is not None]
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

        moves.append({
            "index": i,
            "kind": kind,
            "z0": round(z0, 3),
            "z1": round(z1, 3),
            "start": round(a, 3),
            "end": round(b, 3),
            "words": len(in_range),
            "wps": round(wps, 2),
        })
    return moves
