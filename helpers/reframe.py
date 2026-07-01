#!/usr/bin/env python3
"""
reframe.py — recorta vídeo horizontal (16:9) para vertical (9:16)
seguindo o rosto do speaker via rastreamento de face com OpenCV.

Estratégia:
  1. Amostra frames a cada 0.5s para detectar posição X do rosto
  2. Suaviza a trajetória horizontal (moving average) para evitar jumps
  3. Gera um filtro ffmpeg crop+scale dinâmico via arquivo de expressões

Uso:
    python3 reframe.py <video.mp4> [-o output.mp4] [--target reels|stories]
"""

import argparse
import subprocess
import tempfile
import os
import sys
from pathlib import Path

import cv2
import numpy as np


TARGETS = {
    "reels":   {"w": 1080, "h": 1920},
    "stories": {"w": 1080, "h": 1920},
    "square":  {"w": 1080, "h": 1080},
}


def get_video_info(video_path):
    result = subprocess.run([
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", "-show_format", video_path
    ], capture_output=True, text=True)
    import json
    data = json.loads(result.stdout)
    vs = next(s for s in data["streams"] if s["codec_type"] == "video")
    fps_str = vs.get("avg_frame_rate", "30/1")
    num, den = map(int, fps_str.split("/"))
    fps = num / den if den else 30
    return int(vs["width"]), int(vs["height"]), fps, float(data["format"]["duration"])


def detect_face_positions(video_path, sample_interval=0.5):
    """
    Retorna lista de (timestamp, center_x_normalized) onde center_x é 0..1
    relativo à largura do vídeo. Se nenhum rosto: retorna None para esse frame.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        sys.exit(f"Não consegui abrir {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    cv_data = cv2.data.haarcascades
    face_cascade = cv2.CascadeClassifier(cv_data + "haarcascade_frontalface_default.xml")

    positions = []
    frame_interval = max(1, int(fps * sample_interval))
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % frame_interval == 0:
            ts = frame_idx / fps
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(60, 60))

            if len(faces) > 0:
                fx, fy, fw, fh = max(faces, key=lambda r: r[2]*r[3])
                cx = (fx + fw / 2) / w  # normalizado 0..1
            else:
                cx = None

            positions.append((ts, cx))

        frame_idx += 1

    cap.release()
    return positions, w, h


def smooth_positions(positions, window=10):
    """
    Suaviza os valores de cx com moving average.
    Preenche None com o último valor conhecido.
    """
    # preenche nulos com interpolação
    xs = []
    last = 0.5  # default: centro
    for ts, cx in positions:
        if cx is not None:
            last = cx
        xs.append(last)

    # moving average
    kernel = np.ones(window) / window
    smoothed = np.convolve(xs, kernel, mode="same")
    return [(positions[i][0], float(smoothed[i])) for i in range(len(positions))]


def build_crop_filter(smooth_pos, src_w, src_h, target_w, target_h):
    """
    Gera filtro ffmpeg com crop dinâmico baseado nos keyframes de posição.
    Para simplificar, usa a mediana da posição (crop estático suavizado).
    Para tracking real frame-a-frame seria necessário usar vf=sendcmd.
    """
    # aspect ratio do crop necessário no source
    crop_h = src_h
    crop_w = int(crop_h * target_w / target_h)
    crop_w = min(crop_w, src_w)

    if crop_w >= src_w:
        # já é mais estreito que necessário (ex: source quadrado)
        crop_w = src_w
        crop_h = int(src_w * target_h / target_w)

    # posição X do centro de interesse (mediana suavizada)
    median_cx = float(np.median([cx for _, cx in smooth_pos]))
    center_x = int(median_cx * src_w)

    # calcula x do crop garantindo que não sai do frame
    x = center_x - crop_w // 2
    x = max(0, min(x, src_w - crop_w))
    y = 0  # crop vertical: topo

    vf = (
        f"crop={crop_w}:{crop_h}:{x}:{y},"
        f"scale={target_w}:{target_h}"
    )
    return vf, x, center_x


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video")
    parser.add_argument("-o", "--output", default=None)
    parser.add_argument("--target", choices=list(TARGETS.keys()), default="reels")
    parser.add_argument("--sample-interval", type=float, default=0.5)
    parser.add_argument("--smooth-window", type=int, default=15,
                        help="Janela de suavização em frames amostrados (padrão 15)")
    args = parser.parse_args()

    video_path = args.video
    if not os.path.exists(video_path):
        sys.exit(f"Arquivo não encontrado: {video_path}")

    target = TARGETS[args.target]
    stem = Path(video_path).stem
    out_path = args.output or str(Path(video_path).parent / f"{stem}_{args.target}.mp4")

    print(f"  detectando rostos a cada {args.sample_interval}s...")
    positions, src_w, src_h = detect_face_positions(video_path, args.sample_interval)

    detected = sum(1 for _, cx in positions if cx is not None)
    print(f"  {detected}/{len(positions)} frames com rosto detectado")

    if detected == 0:
        print("  ⚠️  nenhum rosto detectado — usando crop central")
        smooth_pos = [(ts, 0.5) for ts, _ in positions]
    else:
        smooth_pos = smooth_positions(positions, args.smooth_window)

    vf, crop_x, center_x = build_crop_filter(
        smooth_pos, src_w, src_h,
        target["w"], target["h"]
    )

    print(f"  crop: x={crop_x}  center_x={center_x}/{src_w}")
    print(f"  filtro: {vf}")
    print(f"  → {out_path}")

    cmd = [
        "ffmpeg", "-i", video_path,
        "-vf", vf,
        "-c:v", "libx264", "-crf", "20", "-preset", "fast",
        "-c:a", "copy",
        out_path, "-y", "-loglevel", "error"
    ]
    result = subprocess.run(cmd)
    if result.returncode == 0:
        size_mb = os.path.getsize(out_path) / 1024 / 1024
        print(f"\ndone: {out_path} ({size_mb:.1f} MB)")
    else:
        sys.exit("Erro no reframe.")


if __name__ == "__main__":
    main()
