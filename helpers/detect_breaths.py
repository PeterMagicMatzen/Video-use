#!/usr/bin/env python3
"""
detect_breaths.py — detecta respiros e sons de respiração no áudio de um vídeo
usando análise de amplitude via ffmpeg, independente do Scribe.

Estratégia:
  1. Extrai áudio em mono
  2. Calcula RMS por janelas de 50ms
  3. Identifica regiões de "atividade baixa mas não-silêncio" (respiros)
     usando limiares configuráveis
  4. Filtra regiões muito curtas ou muito longas
  5. Reporta timestamps e duração de cada respiro detectado

Integração com EDL:
  - Se --edl passado, verifica quais respiros estão dentro de segmentos
  - Gera lista de cortes sugeridos

Uso:
    python3 detect_breaths.py <video.mp4> [--edl edl.json] [--min-ms 80] [--max-ms 800]
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np


def extract_audio_samples(video_path, sample_rate=16000):
    """Extrai áudio como PCM mono via ffmpeg, retorna array numpy."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name

    subprocess.run([
        "ffmpeg", "-i", video_path,
        "-ac", "1", "-ar", str(sample_rate),
        "-f", "wav", tmp_path,
        "-y", "-loglevel", "error"
    ], check=True)

    # lê o WAV manualmente (evita dependência de scipy)
    with open(tmp_path, "rb") as f:
        f.read(44)  # pula header WAV de 44 bytes
        raw = f.read()
    os.unlink(tmp_path)

    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    return samples, sample_rate


def compute_rms(samples, sr, window_ms=50):
    """Calcula RMS por janelas de window_ms milissegundos."""
    window = int(sr * window_ms / 1000)
    n_windows = len(samples) // window
    rms = np.array([
        np.sqrt(np.mean(samples[i*window:(i+1)*window]**2))
        for i in range(n_windows)
    ])
    return rms, window_ms / 1000.0  # retorna RMS e duração de cada janela em s


def detect_breath_regions(rms, window_s,
                           silence_threshold=0.005,
                           breath_min=0.008,
                           breath_max=0.12,
                           min_duration_ms=80,
                           max_duration_ms=800):
    """
    Identifica regiões de respiro:
    - amplitude entre silence_threshold e breath_max (não é silêncio, não é fala)
    - duração entre min_duration_ms e max_duration_ms
    """
    min_windows = int(min_duration_ms / (window_s * 1000))
    max_windows = int(max_duration_ms / (window_s * 1000))

    # classifica cada janela
    is_breath = (rms >= silence_threshold) & (rms <= breath_max)

    # encontra regiões contíguas
    regions = []
    in_region = False
    start = 0

    for i, b in enumerate(is_breath):
        if b and not in_region:
            in_region = True
            start = i
        elif not b and in_region:
            in_region = False
            duration = i - start
            if min_windows <= duration <= max_windows:
                t_start = start * window_s
                t_end = i * window_s
                avg_rms = float(np.mean(rms[start:i]))
                regions.append({
                    "start": round(t_start, 3),
                    "end": round(t_end, 3),
                    "duration_ms": int((t_end - t_start) * 1000),
                    "avg_rms": round(avg_rms, 5),
                })

    # fecha região aberta no final
    if in_region:
        duration = len(is_breath) - start
        if min_windows <= duration <= max_windows:
            t_start = start * window_s
            t_end = len(is_breath) * window_s
            avg_rms = float(np.mean(rms[start:]))
            regions.append({
                "start": round(t_start, 3),
                "end": round(t_end, 3),
                "duration_ms": int((t_end - t_start) * 1000),
                "avg_rms": round(avg_rms, 5),
            })

    return regions


def load_edl_segments(edl_path):
    with open(edl_path) as f:
        edl = json.load(f)
    return edl.get("ranges", [])


def filter_in_segments(breath_regions, segments):
    """Retorna respiros que estão dentro de algum segmento do EDL."""
    inside = []
    for b in breath_regions:
        for seg in segments:
            # verifica sobreposição
            if b["start"] < seg["end"] and b["end"] > seg["start"]:
                inside.append({
                    **b,
                    "segment_beat": seg.get("beat", "?"),
                    "segment_range": f"{seg['start']:.2f}-{seg['end']:.2f}",
                })
                break
    return inside


def calibrate_thresholds(rms):
    """Estima limiares automaticamente baseado na distribuição do RMS."""
    p5  = float(np.percentile(rms, 5))   # silêncio
    p30 = float(np.percentile(rms, 30))  # fala baixa / respiros
    p70 = float(np.percentile(rms, 70))  # fala normal

    silence_threshold = max(p5 * 2, 0.003)
    breath_max = min(p30 * 1.5, p70 * 0.5, 0.15)

    return silence_threshold, breath_max


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video")
    parser.add_argument("--edl", default=None, help="EDL JSON para filtrar por segmento")
    parser.add_argument("--min-ms", type=int, default=80)
    parser.add_argument("--max-ms", type=int, default=800)
    parser.add_argument("--silence-threshold", type=float, default=None,
                        help="RMS mínimo para não ser silêncio (auto se omitido)")
    parser.add_argument("--breath-max", type=float, default=None,
                        help="RMS máximo para ser respiro, não fala (auto se omitido)")
    parser.add_argument("--window-ms", type=int, default=50)
    args = parser.parse_args()

    if not os.path.exists(args.video):
        sys.exit(f"Arquivo não encontrado: {args.video}")

    print(f"  extraindo áudio de {args.video}...")
    samples, sr = extract_audio_samples(args.video)

    print(f"  calculando RMS ({args.window_ms}ms por janela)...")
    rms, window_s = compute_rms(samples, sr, args.window_ms)

    # calibração automática
    silence_thr, breath_max = calibrate_thresholds(rms)
    if args.silence_threshold is not None:
        silence_thr = args.silence_threshold
    if args.breath_max is not None:
        breath_max = args.breath_max

    print(f"  limiares: silêncio < {silence_thr:.4f} | respiro < {breath_max:.4f}")

    breaths = detect_breath_regions(
        rms, window_s,
        silence_threshold=silence_thr,
        breath_max=breath_max,
        min_duration_ms=args.min_ms,
        max_duration_ms=args.max_ms,
    )

    print(f"  {len(breaths)} evento(s) detectado(s) no total\n")

    if args.edl:
        segments = load_edl_segments(args.edl)
        breaths = filter_in_segments(breaths, segments)
        print(f"  {len(breaths)} dentro de segmentos do EDL:\n")
        label = "beat"
    else:
        label = None

    if not breaths:
        print("  ✅  nenhum respiro detectado nos segmentos.")
        return

    for b in breaths:
        extra = ""
        if label:
            extra = f"  [{b['segment_beat']:<20} src {b['segment_range']}]"
        print(f"  {b['start']:7.3f}s – {b['end']:7.3f}s  "
              f"({b['duration_ms']}ms  rms={b['avg_rms']:.4f}){extra}")

    # salva JSON
    stem = Path(args.video).stem
    out_json = str(Path(args.video).parent / "edit" / f"breaths_{stem}.json")
    os.makedirs(os.path.dirname(out_json), exist_ok=True)
    with open(out_json, "w") as f:
        json.dump(breaths, f, indent=2)
    print(f"\n  salvo: {out_json}")


if __name__ == "__main__":
    main()
