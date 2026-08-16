"""Apply a color grade to a video via ffmpeg filter chain.

Two modes:

  1. Preset mode — named looks. Default names (`none`, `natural`) apply
     no filter. `cinematic` is a 2% contrast tick with no hue shift.

  2. Auto mode — correct only broken exposure. Well-shot footage gets
     no filter. Caps are ±3%. No hue shift, no saturation change.

Usage:
    python helpers/grade.py <input> -o <output>                   # auto mode
    python helpers/grade.py <input> -o <output> --preset warm_cinematic
    python helpers/grade.py <input> -o <output> --filter 'eq=contrast=1.1'
    python helpers/grade.py --print-preset warm_cinematic         # print filter only
    python helpers/grade.py --analyze <input>                     # print auto-grade analysis

Can also be imported by render.py: `get_preset(name)` and `auto_grade_for_clip(path, edl_range)`.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


PRESETS: dict[str, str] = {
    # Default look: the source, unchanged. Skin and rooms stay as shot.
    "none": "",
    "natural": "",
    "subtle": "",

    # Barely-there cinematic: a whisper of midtone contrast, no hue shift,
    # no sat pull, no crushed blacks. Should not read as "graded".
    "cinematic": "eq=contrast=1.02:gamma=1.01:saturation=1.0",

    # Kept as a name so old EDLs still resolve. Same as cinematic — the
    # old teal/orange + crushed-black look is gone.
    "warm_cinematic": "eq=contrast=1.02:gamma=1.01:saturation=1.0",

    # Tiny contrast only. No S-curve. Used to be a punchy film curve.
    "neutral_punch": "eq=contrast=1.02:saturation=1.0",
}


def get_preset(name: str) -> str:
    """Return the ffmpeg filter string for a preset name. Empty string for 'none'."""
    if name not in PRESETS:
        raise KeyError(
            f"unknown preset '{name}'. Available: {', '.join(sorted(PRESETS))}"
        )
    return PRESETS[name]


# -------- Auto grade (data-driven, per-clip) --------------------------------


def _sample_frame_stats(
    video: Path,
    start: float,
    duration: float,
    n_samples: int = 10,
) -> dict[str, float]:
    """Sample N frames from a range and compute brightness/contrast/saturation stats.

    Uses ffmpeg's `signalstats` filter which gives us YMIN, YMAX, YAVG, SATAVG
    etc. in the metadata. We average across the sample range.

    Returns:
        {
          "y_mean":   mean Y (luma) in 0..1,
          "y_std":    approximate stddev of Y across samples (0..1),
          "sat_mean": mean saturation in 0..1,
        }
    """
    # Use signalstats + metadata=print to get per-frame stats
    # Sample fps = n_samples / duration, clamped so we don't over-sample short clips
    fps = max(0.5, min(n_samples / max(duration, 0.1), 10.0))

    with tempfile.NamedTemporaryFile(mode="w+", suffix=".txt", delete=False) as f:
        metadata_path = f.name

    try:
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-nostats",
            "-ss", f"{start:.3f}",
            "-i", str(video),
            "-t", f"{duration:.3f}",
            "-vf", f"fps={fps:.2f},signalstats,metadata=print:file={metadata_path}",
            "-f", "null", "-",
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Parse signalstats metadata. Signalstats reports values in the NATIVE
        # bit depth of the decoded frame (8-bit → 0-255, 10-bit → 0-1023). We
        # read YBITDEPTH and normalize by (2^depth - 1) so downstream math is
        # in 0..1 regardless of source bit depth.
        y_avgs: list[float] = []
        y_mins: list[float] = []
        y_maxs: list[float] = []
        sat_avgs: list[float] = []
        bit_depth: int = 8

        def _parse_value(line: str) -> float | None:
            try:
                return float(line.rsplit("=", 1)[1])
            except (ValueError, IndexError):
                return None

        with open(metadata_path) as f:
            for line in f:
                line = line.strip()
                if "lavfi.signalstats.YBITDEPTH" in line:
                    v = _parse_value(line)
                    if v is not None:
                        bit_depth = int(v)
                elif "lavfi.signalstats.YAVG" in line:
                    v = _parse_value(line)
                    if v is not None:
                        y_avgs.append(v)
                elif "lavfi.signalstats.YMIN" in line:
                    v = _parse_value(line)
                    if v is not None:
                        y_mins.append(v)
                elif "lavfi.signalstats.YMAX" in line:
                    v = _parse_value(line)
                    if v is not None:
                        y_maxs.append(v)
                elif "lavfi.signalstats.SATAVG" in line:
                    v = _parse_value(line)
                    if v is not None:
                        sat_avgs.append(v)

        if not y_avgs:
            # Analysis failed — return neutral defaults (no correction)
            return {"y_mean": 0.5, "y_std": 0.18, "sat_mean": 0.25}

        # Normalize by native bit-depth max value
        max_val = (2 ** bit_depth) - 1

        y_mean = (sum(y_avgs) / len(y_avgs)) / max_val
        y_range = (
            ((sum(y_maxs) / len(y_maxs)) - (sum(y_mins) / len(y_mins))) / max_val
            if y_maxs and y_mins
            else 0.7
        )
        sat_mean = ((sum(sat_avgs) / len(sat_avgs)) / max_val) if sat_avgs else 0.25

        return {
            "y_mean": y_mean,
            "y_std": y_range / 4.0,  # range ÷ 4 ≈ stddev for normal-ish distributions
            "sat_mean": sat_mean,
        }
    finally:
        Path(metadata_path).unlink(missing_ok=True)


def auto_grade_for_clip(
    video: Path,
    start: float = 0.0,
    duration: float | None = None,
    verbose: bool = False,
) -> tuple[str, dict[str, float]]:
    """Analyze a clip range and emit a correction only if the image is broken.

    Returns (filter_string, stats_dict). Well-exposed footage gets an empty
    filter — we do not "make it cinematic". Caps are ±3%. No hue shift,
    no saturation change. Only:
      - Severe underexposure (y_mean < 0.30) → tiny gamma lift
      - Extremely flat range (y_range < 0.45) → tiny contrast
    """
    if duration is None:
        # Probe duration
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video),
        ]
        try:
            duration = float(subprocess.check_output(probe_cmd).decode().strip())
        except Exception:
            duration = 10.0

    stats = _sample_frame_stats(video, start, duration)

    y_mean = stats["y_mean"]
    y_range = stats["y_std"] * 4.0  # back to range
    sat_mean = stats["sat_mean"]

    # ------ Decision rules ---------------------------------------------------
    # Leave well-exposed footage alone. Never grade for taste.

    contrast_adj = 1.0
    if y_range < 0.45:
        t = max(0.0, min(1.0, (y_range - 0.30) / 0.15))
        contrast_adj = 1.03 - 0.03 * t

    gamma_adj = 1.0
    if y_mean < 0.30:
        t = max(0.0, min(1.0, (y_mean - 0.18) / 0.12))
        gamma_adj = 1.03 - 0.03 * t

    sat_adj = 1.0
    _ = sat_mean  # saturation is never touched

    contrast_adj = max(1.0, min(1.03, contrast_adj))
    gamma_adj = max(1.0, min(1.03, gamma_adj))
    sat_adj = 1.0

    # Build filter string
    eq_parts = []
    if abs(contrast_adj - 1.0) > 0.005:
        eq_parts.append(f"contrast={contrast_adj:.3f}")
    if abs(gamma_adj - 1.0) > 0.005:
        eq_parts.append(f"gamma={gamma_adj:.3f}")
    if abs(sat_adj - 1.0) > 0.005:
        eq_parts.append(f"saturation={sat_adj:.3f}")

    if not eq_parts:
        filter_string = ""
    else:
        filter_string = "eq=" + ":".join(eq_parts)

    if verbose:
        print(f"  auto-grade stats:")
        print(f"    y_mean={y_mean:.3f}  y_range={y_range:.3f}  sat_mean={sat_mean:.3f}")
        print(f"    → contrast={contrast_adj:.3f}  gamma={gamma_adj:.3f}  sat={sat_adj:.3f}")
        print(f"    → filter: {filter_string or '(empty)'}")

    return filter_string, stats


def apply_grade(input_path: Path, output_path: Path, filter_string: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not filter_string:
        cmd = [
            "ffmpeg", "-y", "-i", str(input_path),
            "-c", "copy", str(output_path),
        ]
    else:
        cmd = [
            "ffmpeg", "-y", "-i", str(input_path),
            "-vf", filter_string,
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-c:a", "copy",
            "-movflags", "+faststart",
            str(output_path),
        ]
    subprocess.run(cmd, check=True)


def main() -> None:
    from stdio import configure_stdio
    configure_stdio()
    ap = argparse.ArgumentParser(description="Apply a color grade via ffmpeg filter chain")
    ap.add_argument("input", type=Path, nargs="?", help="Input video")
    ap.add_argument("-o", "--output", type=Path, help="Output video")
    ap.add_argument(
        "--preset",
        type=str,
        default=None,
        choices=list(PRESETS.keys()),
        help="Grade preset. Omit for auto mode (default).",
    )
    ap.add_argument(
        "--filter",
        type=str,
        default=None,
        help="Raw ffmpeg filter string. Overrides --preset.",
    )
    ap.add_argument(
        "--analyze",
        type=Path,
        default=None,
        help="Analyze a clip and print the auto-grade filter it would produce. No output written.",
    )
    ap.add_argument(
        "--print-preset",
        type=str,
        default=None,
        help="Print the filter string for a preset and exit. No input/output needed.",
    )
    ap.add_argument(
        "--list-presets",
        action="store_true",
        help="List available presets and exit.",
    )
    args = ap.parse_args()

    if args.list_presets:
        for name, f in PRESETS.items():
            print(f"{name}:")
            print(f"  {f}" if f else "  (no filter)")
            print()
        return

    if args.print_preset is not None:
        print(get_preset(args.print_preset))
        return

    if args.analyze is not None:
        if not args.analyze.exists():
            sys.exit(f"input not found: {args.analyze}")
        filter_string, stats = auto_grade_for_clip(args.analyze, verbose=True)
        print(f"\nfilter: {filter_string or '(none)'}")
        print(f"stats:  {json.dumps(stats, indent=2)}")
        return

    if not args.input or not args.output:
        ap.error("input and -o/--output are required unless using --analyze/--print-preset/--list-presets")

    if not args.input.exists():
        sys.exit(f"input not found: {args.input}")

    # Decide filter string
    if args.filter is not None:
        filter_string = args.filter
    elif args.preset is not None:
        filter_string = get_preset(args.preset)
    else:
        # Auto mode (default)
        filter_string, _ = auto_grade_for_clip(args.input, verbose=True)

    print(f"grading {args.input.name} → {args.output.name}")
    if filter_string:
        print(f"  filter: {filter_string[:120]}{'...' if len(filter_string) > 120 else ''}")
    else:
        print("  filter: (none — copy)")

    apply_grade(args.input, args.output, filter_string)
    print(f"done: {args.output}")


if __name__ == "__main__":
    main()
