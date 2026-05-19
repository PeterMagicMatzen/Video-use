"""srt_video_editor — minimal viable version.

Reads script.srt + edit_plan.json, validates that their ids match, and
prints the planned source-time range for each subtitle cue. Does NOT
touch video — this is the starting scaffold before any ffmpeg work.

Self-contained on purpose: no imports from helpers/ so the whole flow
fits in one readable file.

Usage:
    python srt_video_editor.py
    python srt_video_editor.py --srt input/script.srt --plan input/edit_plan.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


# ---------- timestamp helpers ----------

_TS_RE = re.compile(r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})")


def parse_ts(s: str) -> float:
    """Parse 'HH:MM:SS,ms' or 'HH:MM:SS.ms' to seconds."""
    m = _TS_RE.fullmatch(s.strip())
    if not m:
        raise ValueError(f"bad timestamp: {s!r}")
    h, mn, sec, ms = m.groups()
    return int(h) * 3600 + int(mn) * 60 + int(sec) + int(ms.ljust(3, "0")) / 1000.0


def format_ts(seconds: float) -> str:
    total_ms = int(round(seconds * 1000))
    h, rem = divmod(total_ms, 3600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# ---------- parsers ----------


def parse_srt(path: Path) -> list[dict]:
    """Return a list of {id, start, end, text} in file order.

    Tolerates UTF-8 with or without BOM, CRLF / LF line endings, and
    SRT cue settings ('position:90% align:start') trailing the time line.
    """
    raw = path.read_text(encoding="utf-8-sig")
    cues: list[dict] = []
    for block in re.split(r"\r?\n\r?\n+", raw.strip()):
        lines = [ln for ln in block.splitlines() if ln.strip()]
        if len(lines) < 2:
            continue
        try:
            cid = int(lines[0].strip())
        except ValueError:
            raise SystemExit(f"SRT id line is not an integer: {lines[0]!r}")
        if "-->" not in lines[1]:
            raise SystemExit(f"SRT block missing '-->' time line: {lines[1]!r}")
        left, right = lines[1].split("-->", 1)
        start = parse_ts(left.strip().split()[-1])
        end = parse_ts(right.strip().split()[0])
        text = "\n".join(lines[2:])
        cues.append({"id": cid, "start": start, "end": end, "text": text})
    if not cues:
        raise SystemExit(f"SRT has no cues: {path}")
    return cues


def parse_plan(path: Path) -> list[dict]:
    """Return a list of {id, source_start, source_end}. Only Form A is
    accepted here (a flat JSON array); Form B is out of scope for the
    minimal version."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit(
            "edit_plan.json must be a JSON array of "
            "{id, source_start, source_end} objects (Form A)."
        )
    out: list[dict] = []
    for row in data:
        try:
            out.append({
                "id": int(row["id"]),
                "source_start": parse_ts(row["source_start"]),
                "source_end": parse_ts(row["source_end"]),
            })
        except (KeyError, ValueError) as e:
            raise SystemExit(f"plan row {row!r}: {e}")
    return out


# ---------- validation ----------


def validate_ids(cues: list[dict], plan: list[dict]) -> None:
    """Each id must appear exactly once in both sides, and the two id sets
    must be equal. Any deviation is a hard failure with a clear message.
    """
    cue_ids = [c["id"] for c in cues]
    plan_ids = [p["id"] for p in plan]

    dup_cue = {i for i in cue_ids if cue_ids.count(i) > 1}
    if dup_cue:
        raise SystemExit(f"SRT has duplicate ids: {sorted(dup_cue)}")
    dup_plan = {i for i in plan_ids if plan_ids.count(i) > 1}
    if dup_plan:
        raise SystemExit(f"edit_plan has duplicate ids: {sorted(dup_plan)}")

    only_srt = set(cue_ids) - set(plan_ids)
    only_plan = set(plan_ids) - set(cue_ids)
    if only_srt or only_plan:
        msg = []
        if only_srt:
            msg.append(f"in SRT but missing in plan: {sorted(only_srt)}")
        if only_plan:
            msg.append(f"in plan but missing in SRT: {sorted(only_plan)}")
        raise SystemExit("id mismatch: " + "; ".join(msg))


# ---------- report ----------


def print_report(cues: list[dict], plan: list[dict]) -> None:
    plan_by_id = {p["id"]: p for p in plan}
    print(f"{len(cues)} cue(s), all ids matched.")
    print()
    header = f"  {'ID':>3}  {'OUTPUT (cue)':<23}  {'SOURCE (planned)':<23}  TEXT"
    print(header)
    print(f"  {'-' * 3}  {'-' * 23}  {'-' * 23}  {'-' * 4}")
    for cue in sorted(cues, key=lambda c: c["id"]):
        p = plan_by_id[cue["id"]]
        out_range = f"{format_ts(cue['start'])} -> {format_ts(cue['end'])}"
        src_range = f"{format_ts(p['source_start'])} -> {format_ts(p['source_end'])}"
        preview = cue["text"].replace("\n", " ")
        if len(preview) > 50:
            preview = preview[:47] + "..."
        print(f"  {cue['id']:>3}  {out_range:<23}  {src_range:<23}  {preview}")


# ---------- entry ----------


def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Minimal SRT-driven editor. Reads script.srt + edit_plan.json, "
            "validates id matching, prints the planned source range for each "
            "cue. No ffmpeg, no actual cutting."
        ),
    )
    ap.add_argument("--srt", type=Path, default=Path("input/script.srt"))
    ap.add_argument("--plan", type=Path, default=Path("input/edit_plan.json"))
    args = ap.parse_args()

    for p in (args.srt, args.plan):
        if not p.is_file():
            raise SystemExit(f"file not found: {p}")

    cues = parse_srt(args.srt)
    plan = parse_plan(args.plan)
    validate_ids(cues, plan)
    print_report(cues, plan)


if __name__ == "__main__":
    main()
