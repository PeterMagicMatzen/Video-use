#!/usr/bin/env python3
"""
export_formats.py — exporta um vídeo final em múltiplos formatos de uma vez.

Formatos disponíveis:
  reels     1080x1920  9:16  vertical   Instagram Reels / TikTok / Shorts
  feed      1080x1080  1:1   quadrado   Instagram Feed
  stories   1080x1920  9:16  vertical   Stories (com margens laterais se necessário)
  landscape 1920x1080  16:9  horizontal YouTube / LinkedIn

Uso:
    python3 export_formats.py <final.mp4> [--formats reels feed stories landscape] [--out-dir <dir>]
"""

import argparse
import subprocess
import os
import sys
from pathlib import Path


FORMATS = {
    "reels": {
        "w": 1080, "h": 1920,
        "desc": "Instagram Reels / TikTok / YouTube Shorts (9:16)",
        "crop": "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
    },
    "feed": {
        "w": 1080, "h": 1080,
        "desc": "Instagram Feed (1:1)",
        "crop": "scale=1080:1080:force_original_aspect_ratio=increase,crop=1080:1080",
    },
    "stories": {
        "w": 1080, "h": 1920,
        "desc": "Stories com margens (9:16 com padding)",
        # encaixa o vídeo dentro de 1080x1920 com barras pretas se necessário
        "crop": "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black",
    },
    "landscape": {
        "w": 1920, "h": 1080,
        "desc": "YouTube / LinkedIn (16:9)",
        "crop": "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080",
    },
}


def get_video_info(video_path):
    result = subprocess.run([
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", video_path
    ], capture_output=True, text=True)
    import json
    data = json.loads(result.stdout)
    vs = next(s for s in data["streams"] if s["codec_type"] == "video")
    return int(vs["width"]), int(vs["height"])


def export_format(video_path, fmt_name, fmt, out_dir, crf=23):
    stem = Path(video_path).stem
    out_path = os.path.join(out_dir, f"{stem}_{fmt_name}.mp4")

    vf = fmt["crop"]

    cmd = [
        "ffmpeg", "-i", video_path,
        "-vf", vf,
        "-c:v", "libx264", "-crf", str(crf), "-preset", "fast",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        out_path, "-y", "-loglevel", "error"
    ]

    print(f"  [{fmt_name}] {fmt['desc']} → {out_path}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"  ⚠️  erro ao exportar {fmt_name}", file=sys.stderr)
        return False

    size_mb = os.path.getsize(out_path) / 1024 / 1024
    print(f"         ✓ {size_mb:.1f} MB")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video")
    parser.add_argument("--formats", nargs="+",
                        choices=list(FORMATS.keys()),
                        default=["reels", "feed", "landscape"],
                        help="Formatos a exportar (padrão: reels feed landscape)")
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--crf", type=int, default=23,
                        help="CRF de qualidade (18=alta, 28=comprimido, padrão 23)")
    args = parser.parse_args()

    video_path = args.video
    if not os.path.exists(video_path):
        sys.exit(f"Arquivo não encontrado: {video_path}")

    out_dir = args.out_dir or str(Path(video_path).parent / "exports")
    os.makedirs(out_dir, exist_ok=True)

    w, h = get_video_info(video_path)
    print(f"  fonte: {w}x{h}  →  exportando {len(args.formats)} formato(s)...\n")

    ok = 0
    for fmt_name in args.formats:
        if export_format(video_path, fmt_name, FORMATS[fmt_name], out_dir, args.crf):
            ok += 1

    print(f"\ndone: {ok}/{len(args.formats)} formatos em {out_dir}/")


if __name__ == "__main__":
    main()
