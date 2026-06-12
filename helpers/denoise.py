#!/usr/bin/env python3
"""
denoise.py — redução de ruído de áudio em vídeos.

Modos:
  light   — ruído ambiente leve (ar condicionado, sala)
  medium  — microfone com hiss moderado (padrão)
  strong  — vento, ruído forte (como o 163131)
  custom  — passa filtros ffmpeg diretamente via --filter

Uso:
    python3 denoise.py <video.mp4> [--mode medium] [-o output.mp4]
    python3 denoise.py <video.mp4> --filter "afftdn=nf=-25" -o saida.mp4
"""

import argparse
import subprocess
import os
import sys
from pathlib import Path


MODES = {
    "light": {
        "desc": "ruído leve (sala, AC)",
        # anlmdn: Non-Local Means Denoising (gentil, preserva voz)
        "filter": "anlmdn=s=0.00005:p=0.002:r=0.002:m=15",
    },
    "medium": {
        "desc": "ruído moderado (microfone, hiss) — padrão",
        # afftdn: FFT-based denoising + highpass para remover sub-bass
        "filter": "afftdn=nf=-20,highpass=f=80",
    },
    "strong": {
        "desc": "ruído forte (vento, microfone ruim)",
        # arnndn: RNN-based denoising (mais agressivo)
        # + afftdn para o que sobrar
        # + highpass para fundos
        "filter": "arnndn=m=bd.rnnn,afftdn=nf=-15,highpass=f=100",
    },
    "wind": {
        "desc": "vento intenso (como nos primeiros 45s do 163131)",
        "filter": "highpass=f=200,lowpass=f=8000,arnndn=m=bd.rnnn,afftdn=nf=-10",
    },
}

# modelo arnndn (baixa automaticamente se não existir)
ARNNDN_MODEL_URL = "https://github.com/GregorR/rnnoise-models/raw/master/beguiling-drafter-2018-08-30/bd.rnnn"


def ensure_arnndn_model():
    model_dir = Path.home() / ".local" / "share" / "arnndn"
    model_path = model_dir / "bd.rnnn"
    if not model_path.exists():
        model_dir.mkdir(parents=True, exist_ok=True)
        print("  baixando modelo arnndn...")
        subprocess.run(["curl", "-sL", ARNNDN_MODEL_URL, "-o", str(model_path)], check=True)
    return str(model_path)


def denoise(video_path, audio_filter, out_path):
    cmd = [
        "ffmpeg", "-i", video_path,
        "-af", audio_filter,
        "-c:v", "copy",          # vídeo sem re-encode
        "-c:a", "aac", "-b:a", "192k",
        out_path, "-y", "-loglevel", "error"
    ]
    result = subprocess.run(cmd)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video")
    parser.add_argument("--mode", choices=list(MODES.keys()), default="medium")
    parser.add_argument("--filter", dest="custom_filter", default=None,
                        help="Filtro ffmpeg customizado (substitui --mode)")
    parser.add_argument("-o", "--output", default=None)
    args = parser.parse_args()

    video_path = args.video
    if not os.path.exists(video_path):
        sys.exit(f"Arquivo não encontrado: {video_path}")

    # resolve filtro
    if args.custom_filter:
        audio_filter = args.custom_filter
        mode_desc = "custom"
    else:
        mode = MODES[args.mode]
        audio_filter = mode["filter"]
        mode_desc = f"{args.mode} — {mode['desc']}"

        # se o modo usa arnndn, garante o modelo
        if "arnndn" in audio_filter:
            model_path = ensure_arnndn_model()
            audio_filter = audio_filter.replace("m=bd.rnnn", f"m={model_path}")

    stem = Path(video_path).stem
    out_path = args.output or str(Path(video_path).parent / f"{stem}_denoised.mp4")

    print(f"  modo: {mode_desc}")
    print(f"  filtro: {audio_filter}")
    print(f"  → {out_path}")

    if denoise(video_path, audio_filter, out_path):
        size_mb = os.path.getsize(out_path) / 1024 / 1024
        print(f"\ndone: {out_path} ({size_mb:.1f} MB)")
    else:
        sys.exit("Erro na redução de ruído.")


if __name__ == "__main__":
    main()
