#!/usr/bin/env python3
"""
thumbnail.py — extrai os melhores frames de um vídeo como sugestões de thumbnail.

Pontuação por frame:
  - rosto detectado e centralizado (+++)
  - olhos abertos (+++)
  - boca fechada (++)
  - nitidez / sem blur (+)
  - rosto grande o suficiente (+)

Uso:
    python3 thumbnail.py <video.mp4> [--out-dir <dir>] [--top N] [--interval 0.5]
"""

import argparse
import subprocess
import tempfile
import os
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def extract_frames(video_path, interval_s=0.5, out_dir=None):
    """Extrai frames em intervalos regulares via ffmpeg."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", video_path],
        capture_output=True, text=True
    )
    duration = float(result.stdout.strip() or 0)
    if duration == 0:
        sys.exit(f"Não consegui ler a duração de {video_path}")

    frames = []
    t = 0.0
    while t < duration:
        out_path = os.path.join(out_dir, f"frame_{t:.3f}.jpg")
        subprocess.run([
            "ffmpeg", "-ss", str(t), "-i", video_path,
            "-vframes", "1", "-q:v", "2",
            "-vf", "scale=iw*min(1080/iw\\,1920/ih):ih*min(1080/iw\\,1920/ih)",
            out_path, "-y", "-loglevel", "error"
        ], check=False)
        if os.path.exists(out_path):
            frames.append((t, out_path))
        t = round(t + interval_s, 3)
    return frames


def sharpness(gray):
    """Laplacian variance — maior = mais nítido."""
    return cv2.Laplacian(gray, cv2.CV_64F).var()


def score_frame(img_path, face_cascade, eye_cascade, mouth_cascade):
    img = cv2.imread(img_path)
    if img is None:
        return 0, None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    faces = face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(80, 80))
    if len(faces) == 0:
        return sharpness(gray) * 0.1, None  # sem rosto = penaliza

    # pega o maior rosto
    x, y, fw, fh = max(faces, key=lambda r: r[2] * r[3])
    face_roi = gray[y:y+fh, x:x+fw]
    face_img = img[y:y+fh, x:x+fw]

    score = 0.0

    # tamanho do rosto relativo ao frame
    face_fraction = (fw * fh) / (w * h)
    score += face_fraction * 30

    # centralização horizontal
    cx = x + fw / 2
    center_score = 1 - abs(cx / w - 0.5) * 2   # 1.0 = centrado
    score += center_score * 20

    # posição vertical (rosto no terço superior-central)
    cy = y + fh / 2
    vert_ideal = 0.35
    vert_score = max(0, 1 - abs(cy / h - vert_ideal) * 3)
    score += vert_score * 10

    # olhos detectados
    eyes = eye_cascade.detectMultiScale(face_roi, 1.1, 3, minSize=(20, 20))
    score += len(eyes) * 15

    # boca: penaliza se detectada grande (boca aberta)
    mouths = mouth_cascade.detectMultiScale(
        face_roi[int(fh*0.5):], 1.1, 3, minSize=(30, 15))
    if len(mouths) > 0:
        mouth_area = max(m[2]*m[3] for m in mouths) / (fw * fh)
        score -= mouth_area * 100  # boca aberta = penaliza

    # nitidez
    sharp = sharpness(face_roi)
    score += min(sharp / 100, 20)  # cap em 20 pts

    return score, (x, y, fw, fh)


def make_contact_sheet(top_frames, video_name, out_path):
    """Gera um PNG com os top frames lado a lado."""
    n = len(top_frames)
    if n == 0:
        return
    thumbs = []
    for ts, img_path, sc, _ in top_frames:
        img = Image.open(img_path).convert("RGB")
        img.thumbnail((320, 320))
        thumbs.append((ts, img, sc))

    cols = min(n, 5)
    rows = (n + cols - 1) // cols
    tw, th = thumbs[0][1].size
    pad = 10
    header = 50
    sheet_w = cols * tw + (cols + 1) * pad
    sheet_h = rows * (th + 30) + (rows + 1) * pad + header

    sheet = Image.new("RGB", (sheet_w, sheet_h), (20, 20, 20))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
        font_title = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 18)
    except Exception:
        font = font_title = ImageFont.load_default()

    draw.text((pad, 12), f"Thumbnails sugeridos — {video_name}", fill=(255,255,255), font=font_title)

    for i, (ts, img, sc) in enumerate(thumbs):
        col = i % cols
        row = i // cols
        x = pad + col * (tw + pad)
        y = header + pad + row * (th + 30 + pad)
        sheet.paste(img, (x, y))
        label = f"#{i+1}  {ts:.1f}s  (score {sc:.0f})"
        draw.text((x, y + th + 4), label, fill=(180, 180, 180), font=font)

    sheet.save(out_path)
    print(f"  contact sheet → {out_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video")
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--interval", type=float, default=0.5,
                        help="Intervalo entre frames em segundos (padrão 0.5)")
    args = parser.parse_args()

    video_path = args.video
    video_name = Path(video_path).stem

    out_dir = args.out_dir or str(Path(video_path).parent / "edit" / "thumbnails")
    os.makedirs(out_dir, exist_ok=True)

    cv_data = cv2.data.haarcascades
    face_cascade  = cv2.CascadeClassifier(cv_data + "haarcascade_frontalface_default.xml")
    eye_cascade   = cv2.CascadeClassifier(cv_data + "haarcascade_eye.xml")
    mouth_cascade = cv2.CascadeClassifier(cv_data + "haarcascade_smile.xml")

    print(f"  extraindo frames a cada {args.interval}s...")
    with tempfile.TemporaryDirectory() as tmp:
        frames = extract_frames(video_path, args.interval, tmp)
        print(f"  {len(frames)} frames — pontuando...")

        scored = []
        for ts, img_path in frames:
            sc, face_box = score_frame(img_path, face_cascade, eye_cascade, mouth_cascade)
            scored.append((ts, img_path, sc, face_box))

        scored.sort(key=lambda x: -x[2])
        top = scored[:args.top]

        # salva os top frames
        saved = []
        for rank, (ts, img_path, sc, box) in enumerate(top, 1):
            dst = os.path.join(out_dir, f"thumb_{rank:02d}_{ts:.1f}s.jpg")
            img = cv2.imread(img_path)
            if img is not None:
                cv2.imwrite(dst, img, [cv2.IMWRITE_JPEG_QUALITY, 95])
            saved.append((ts, dst, sc, box))
            print(f"  #{rank}  t={ts:.1f}s  score={sc:.1f}  → {dst}")

        make_contact_sheet(
            [(ts, p, sc, b) for ts, p, sc, b in saved],
            video_name,
            os.path.join(out_dir, f"{video_name}_thumbnails.png")
        )

    print(f"\ndone: {args.top} thumbnails em {out_dir}/")


if __name__ == "__main__":
    main()
