FILLERS = {"um", "uh", "uhm", "umm", "uhh", "erm", "er", "hmm", "mm", "mmm", "ehm", "eh"}
PAD = 0.12
MIN_KEEP = 0.15


def _norm(text: str) -> str:
    return "".join(c for c in text.lower() if c.isalpha())


def compute_spans(words: list, duration: float, pause_threshold: float, remove_fillers: bool) -> list:
    items = [w for w in words if w.get("type") == "word" and w.get("start") is not None]
    spans = []
    if not items:
        return spans

    if items[0]["start"] > pause_threshold:
        spans.append(_span(0.0, max(0.0, items[0]["start"] - PAD), "pause", "silence"))
    for prev, nxt in zip(items, items[1:]):
        gap = nxt["start"] - prev["end"]
        if gap > pause_threshold:
            spans.append(_span(prev["end"] + PAD, nxt["start"] - PAD, "pause", f"{gap:.1f}s pause"))
    if duration and duration - items[-1]["end"] > pause_threshold:
        spans.append(_span(items[-1]["end"] + PAD, duration, "pause", "trailing silence"))

    if remove_fillers:
        for w in items:
            if _norm(w.get("text", "")) in FILLERS:
                spans.append(_span(max(0.0, w["start"] - 0.03), w["end"] + 0.03, "filler", w["text"].strip()))

    spans = [s for s in spans if s["end"] - s["start"] > 0.05]
    spans.sort(key=lambda s: s["start"])
    return _merge(spans)


def _span(start: float, end: float, kind: str, label: str) -> dict:
    return {
        "id": f"{kind}-{int(round(start * 1000))}",
        "start": round(start, 3),
        "end": round(end, 3),
        "type": kind,
        "label": label,
    }


def _merge(spans: list) -> list:
    out = []
    for s in spans:
        if out and s["start"] <= out[-1]["end"]:
            out[-1]["end"] = max(out[-1]["end"], s["end"])
            if s["type"] == "pause":
                out[-1]["type"] = "pause"
        else:
            out.append(dict(s))
    return out


def keep_ranges(duration: float, spans: list, disabled: set) -> list:
    active = [s for s in spans if s["id"] not in disabled]
    ranges = []
    cursor = 0.0
    for s in active:
        if s["start"] - cursor > MIN_KEEP:
            ranges.append([round(cursor, 3), round(s["start"], 3)])
        cursor = max(cursor, s["end"])
    if duration - cursor > MIN_KEEP:
        ranges.append([round(cursor, 3), round(duration, 3)])
    return ranges or [[0.0, round(duration, 3)]]
