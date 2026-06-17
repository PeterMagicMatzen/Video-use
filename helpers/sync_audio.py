"""Precise multicam audio sync via GCC-PHAT cross-correlation.

The standard cross-correlation peak between mismatched microphones is
broad and ambiguous. GCC-PHAT (Generalized Cross-Correlation with Phase
Transform) whitens the spectrum before correlating — the peak becomes
sharp regardless of mic frequency-response mismatch or room reverb.

This is the audio-engineering standard for multicam sync. Sub-frame
accurate, robust between dissimilar microphones (e.g. studio mic vs
on-camera mic).

Inputs:
  - A reference video (the one whose audio you want to keep)
  - One or more target videos
  - Rough sync timestamps for at least one clap or shared transient

Workflow:
  - Extracts a window of audio around each rough timestamp (default 10s)
  - Runs GCC-PHAT to find the precise lag
  - Combines lag with window-start delta → precise source-time offset
  - Reports per-event measurements + averaged final per target

Usage examples:
    # JSON config (recommended)
    uv run python helpers/sync_audio.py --config sync.json

    # CLI flags
    uv run python helpers/sync_audio.py \\
        --reference /path/desk.mp4 \\
        --target A1=/path/c0036.mp4 \\
        --target DJI=/path/dji.mp4 \\
        --event clap_1:reference=6.23,A1=101.03 \\
        --event clap_2:reference=204.72,A1=299.76,DJI=5.02 \\
        --window-default 10 \\
        --window DJI=30 \\
        --out sync_offsets.json

Config file shape:
{
  "reference": {"name": "DESK", "path": "/abs/desk.mp4"},
  "targets":   {"A1": "/abs/c0036.mp4", "DJI": "/abs/dji.mp4"},
  "events": [
    {"name": "clap_1", "times": {"DESK": 6.23, "A1": 101.03}},
    {"name": "clap_2", "times": {"DESK": 204.72, "A1": 299.76, "DJI": 5.02}}
  ],
  "windows": {"_default": 10, "DJI": 30},
  "out": "sync_offsets.json"
}

Output JSON:
{
  "final": {"A1": 95.94, "DJI": -197.17},
  "measurements": [...]
}

Tips:
  - At least one shared sync event per target is required.
  - Multiple events per target enable consistency checks and flag clock drift.
  - If two measurements for the same target disagree by > 0.05s, the script
    prints a warning. The most likely cause is clap-pattern aliasing (3 claps
    spaced ~0.5s create correlation peaks at integer multiples of that period).
    Pick the offset with the highest sharpness, or verify visually.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from scipy import signal
from scipy.io import wavfile

SR = 16000  # 16kHz — enough for transient localization, fast to process
HIGHPASS_HZ = 200  # removes AC/rumble before correlation


def extract_audio(video: Path, start: float, duration: float) -> np.ndarray:
    """Extract mono PCM audio at SR. Returns float32 array in [-1, 1]."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-ss", f"{max(0.0, start):.3f}", "-i", str(video),
        "-t", f"{duration:.3f}",
        "-ac", "1", "-ar", str(SR), "-c:a", "pcm_s16le",
        "-vn", str(tmp_path),
    ]
    subprocess.run(cmd, check=True)
    sr, data = wavfile.read(tmp_path)
    tmp_path.unlink(missing_ok=True)
    if sr != SR:
        raise RuntimeError(f"unexpected sample rate {sr}")
    if data.ndim > 1:
        data = data.mean(axis=1)
    return data.astype(np.float32) / 32768.0


def gcc_phat(reference: np.ndarray, target: np.ndarray) -> tuple[int, float]:
    """Generalized Cross-Correlation with Phase Transform.

    Whitens the cross-power spectrum (keeps only phase, discards amplitude)
    so the correlation peak responds purely to timing. Robust to mismatched
    mic frequency response and room reverb.

    Returns (lag_samples, sharpness).
      lag_samples > 0 means `target` is later than `reference`.
      sharpness = peak_height / mean(|corr|). Larger = more confident.
    """
    sos = signal.butter(4, HIGHPASS_HZ, btype="highpass", fs=SR, output="sos")
    ref_f = signal.sosfilt(sos, reference)
    tgt_f = signal.sosfilt(sos, target)

    n = len(ref_f) + len(tgt_f) - 1
    nfft = 1 << (n - 1).bit_length()
    R = np.fft.rfft(ref_f, nfft)
    T = np.fft.rfft(tgt_f, nfft)
    cross = T * np.conj(R)
    cross /= np.abs(cross) + 1e-9  # PHAT whitening

    corr = np.fft.irfft(cross, nfft)
    corr = np.concatenate((corr[-len(tgt_f) + 1:], corr[:len(ref_f)]))
    lags = np.arange(-len(tgt_f) + 1, len(ref_f))

    peak_idx = int(np.argmax(corr))
    lag = int(lags[peak_idx])
    sharpness = float(corr[peak_idx] / (np.mean(np.abs(corr)) + 1e-9))
    return lag, sharpness


def measure_event(
    ref_path: Path,
    cam_path: Path,
    ref_t: float,
    cam_t: float,
    window: float,
    label: str,
    verbose: bool = True,
) -> dict:
    """Measure precise offset of `cam` relative to `ref` at one shared event."""
    half = window / 2.0
    ref_start = max(0.0, ref_t - half)
    cam_start = max(0.0, cam_t - half)

    if verbose:
        print(f"  {label}  window={window:.0f}s")
        print(f"    REF window: {ref_start:7.2f}–{ref_start + window:7.2f}")
        print(f"    CAM window: {cam_start:7.2f}–{cam_start + window:7.2f}")

    ref_audio = extract_audio(ref_path, ref_start, window)
    cam_audio = extract_audio(cam_path, cam_start, window)

    lag_samples, sharpness = gcc_phat(ref_audio, cam_audio)
    lag_sec = lag_samples / SR

    # cam_time = ref_time + offset
    rough_offset = cam_t - ref_t
    window_delta = cam_start - ref_start
    precise_offset = window_delta + lag_sec

    if verbose:
        print(f"    → precise offset = {precise_offset:+.4f}s  (rough was {rough_offset:+.4f}, lag {lag_sec:+.4f}s within windows, sharpness {sharpness:.1f})")

    return {
        "label": label,
        "rough_offset": round(rough_offset, 4),
        "precise_offset": round(precise_offset, 4),
        "lag_within_windows_sec": round(lag_sec, 4),
        "sharpness": round(sharpness, 2),
        "ref_window_start": round(ref_start, 3),
        "cam_window_start": round(cam_start, 3),
        "window_seconds": window,
    }


def parse_event_arg(s: str) -> dict:
    """Parse --event flag: name:ref=t,cam1=t,cam2=t"""
    name, rest = s.split(":", 1)
    times = {}
    for pair in rest.split(","):
        k, v = pair.split("=", 1)
        times[k.strip()] = float(v.strip())
    return {"name": name.strip(), "times": times}


def load_config(args) -> dict:
    if args.config:
        return json.loads(Path(args.config).read_text())

    if not (args.reference and args.target and args.event):
        sys.exit("Need --config OR (--reference + --target + --event …)")

    ref_name, ref_path = args.reference.split("=", 1) if "=" in args.reference else ("REF", args.reference)
    targets = {}
    for t in args.target:
        k, v = t.split("=", 1)
        targets[k] = v
    events = [parse_event_arg(e) for e in args.event]
    windows = {"_default": args.window_default}
    for w in args.window or []:
        k, v = w.split("=", 1)
        windows[k] = float(v)
    return {
        "reference": {"name": ref_name, "path": ref_path},
        "targets": targets,
        "events": events,
        "windows": windows,
        "out": args.out,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Precise multicam audio sync via GCC-PHAT")
    ap.add_argument("--config", help="JSON config file (overrides CLI flags)")
    ap.add_argument("--reference", help="REF_NAME=/path/to/ref.mp4 (audio anchor)")
    ap.add_argument("--target", action="append", help="TARGET_NAME=/path (repeat for multiple cams)")
    ap.add_argument("--event", action="append", help="name:ref=time,target=time[,target=time] (repeat)")
    ap.add_argument("--window-default", type=float, default=10.0, help="Default window seconds (10)")
    ap.add_argument("--window", action="append", help="Per-target window: TARGET=seconds")
    ap.add_argument("--out", default="sync_offsets.json", help="Output JSON path")
    ap.add_argument("--tolerance", type=float, default=0.05, help="Disagreement threshold across events")
    args = ap.parse_args()

    cfg = load_config(args)
    ref_name = cfg["reference"]["name"]
    ref_path = Path(cfg["reference"]["path"]).resolve()
    targets = {k: Path(v).resolve() for k, v in cfg["targets"].items()}
    events = cfg["events"]
    windows = cfg.get("windows", {"_default": 10.0})
    default_window = windows.get("_default", 10.0)
    tolerance = args.tolerance

    if not ref_path.exists():
        sys.exit(f"reference not found: {ref_path}")
    for k, p in targets.items():
        if not p.exists():
            sys.exit(f"target {k} not found: {p}")

    measurements: list[dict] = []
    by_target: dict[str, list[dict]] = {k: [] for k in targets}

    for ev in events:
        if ref_name not in ev["times"]:
            print(f"  skip {ev['name']}: no reference time")
            continue
        ref_t = ev["times"][ref_name]
        for cam_name, cam_path in targets.items():
            if cam_name not in ev["times"]:
                continue
            cam_t = ev["times"][cam_name]
            window = float(windows.get(cam_name, default_window))
            label = f"{cam_name} {ev['name']}"
            print(f"\nMeasuring {label}:")
            m = measure_event(ref_path, cam_path, ref_t, cam_t, window, label)
            m["target"] = cam_name
            m["event"] = ev["name"]
            measurements.append(m)
            by_target[cam_name].append(m)

    final: dict[str, float] = {}
    print("\n" + "=" * 60)
    print("FINAL OFFSETS")
    print("=" * 60)
    for cam, ms in by_target.items():
        if not ms:
            print(f"  {cam}: no measurements")
            continue
        offsets = [m["precise_offset"] for m in ms]
        spread = max(offsets) - min(offsets) if len(offsets) > 1 else 0.0
        if spread > tolerance:
            print(f"  ⚠️  {cam}: measurements disagree by {spread:.3f}s (> {tolerance}s tolerance)")
            print("      Likely cause: clap-pattern aliasing or genuine clock drift.")
            print("      Per-event offsets:")
            for m in ms:
                print(f"        {m['event']}: {m['precise_offset']:+.4f}  (sharpness {m['sharpness']:.1f})")
            # Pick the highest-sharpness measurement.
            best = max(ms, key=lambda m: m["sharpness"])
            print(f"      → using {best['event']} (highest sharpness): {best['precise_offset']:+.4f}")
            final[cam] = best["precise_offset"]
        else:
            avg = sum(offsets) / len(offsets)
            final[cam] = round(avg, 4)
            print(f"  ✓  {cam}: {avg:+.4f}s  (avg of {len(ms)} event(s), spread {spread*1000:.0f}ms)")

    out_path = Path(cfg.get("out") or args.out).resolve()
    out_path.write_text(json.dumps({"final": final, "measurements": measurements}, indent=2))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
