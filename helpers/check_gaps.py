#!/usr/bin/env python3
"""
check_gaps.py  —  detecta gaps >= MIN_MS dentro de cada segmento do EDL.
Uso:
    python3 check_gaps.py <edl.json> <transcripts_dir> [--min-ms 300]
"""

import json
import sys
import argparse
from pathlib import Path

def load_words(transcript_path):
    with open(transcript_path) as f:
        d = json.load(f)
    return [w for w in d.get("words", []) if w.get("type") == "word"]

def check_edl(edl_path, transcripts_dir, min_ms=300):
    min_s = min_ms / 1000.0

    with open(edl_path) as f:
        edl = json.load(f)

    # index transcripts by source name
    transcripts = {}
    for source_name in edl["sources"]:
        candidates = list(Path(transcripts_dir).glob(f"{source_name}.json"))
        if candidates:
            transcripts[source_name] = load_words(str(candidates[0]))

    problems = []

    for i, seg in enumerate(edl["ranges"]):
        src = seg["source"]
        seg_start = seg["start"]
        seg_end   = seg["end"]
        words = transcripts.get(src, [])

        # words that fall inside this segment
        seg_words = [w for w in words
                     if w["start"] >= seg_start - 0.1
                     and w["end"]   <= seg_end   + 0.1]

        if len(seg_words) < 2:
            continue

        for j in range(len(seg_words) - 1):
            gap_start = seg_words[j]["end"]
            gap_end   = seg_words[j + 1]["start"]
            gap_s     = gap_end - gap_start
            if gap_s >= min_s:
                problems.append({
                    "seg_index": i,
                    "beat": seg.get("beat", f"seg_{i}"),
                    "source_range": f"{seg_start:.2f}-{seg_end:.2f}",
                    "gap_start": gap_start,
                    "gap_end": gap_end,
                    "gap_ms": int(gap_s * 1000),
                    "before": seg_words[j]["text"],
                    "after":  seg_words[j + 1]["text"],
                })

    return problems

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("edl")
    parser.add_argument("transcripts_dir")
    parser.add_argument("--min-ms", type=int, default=300)
    args = parser.parse_args()

    problems = check_edl(args.edl, args.transcripts_dir, args.min_ms)

    if not problems:
        print(f"✅  Nenhum gap >= {args.min_ms}ms encontrado dentro dos segmentos.")
        return

    print(f"⚠️  {len(problems)} gap(s) >= {args.min_ms}ms dentro dos segmentos:\n")
    for p in problems:
        print(f"  [{p['seg_index']:02d}] {p['beat']:<22}  "
              f"gap {p['gap_ms']}ms  "
              f"entre {p['before']!r} ({p['gap_start']:.3f}s) "
              f"→ {p['after']!r} ({p['gap_end']:.3f}s)  "
              f"[source {p['source_range']}]")

if __name__ == "__main__":
    main()
