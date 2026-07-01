#!/usr/bin/env python3
"""Gera uma faixa de legendas como vídeo RGBA usando PIL.
Não requer libass nem freetype no ffmpeg.

Uso:
    python burn_subs_pil.py <srt_path> <duration_s> <out_path> [fps]
"""
from __future__ import annotations
import re, sys, subprocess, tempfile, os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
FONT_SIZE = 60
MARGIN_BOTTOM = int(H * 0.30)   # 30% do fundo — safe zone Reels/TikTok
MAX_LINE_W = int(W * 0.82)
PAD = 12
OUTLINE = 3


def ts_to_s(ts: str) -> float:
    h, m, rest = ts.split(":")
    s, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def parse_srt(path: str) -> list[tuple[float, float, str]]:
    text = Path(path).read_text(encoding="utf-8")
    blocks = re.split(r"\n{2,}", text.strip())
    cues: list[tuple[float, float, str]] = []
    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 2:
            continue
        # find timestamp line
        ts_line = None
        text_lines: list[str] = []
        for i, line in enumerate(lines):
            if "-->" in line:
                ts_line = line
                text_lines = lines[i + 1:]
                break
        if ts_line is None:
            continue
        m = re.match(r"(\S+)\s+-->\s+(\S+)", ts_line)
        if not m:
            continue
        start = ts_to_s(m.group(1))
        end = ts_to_s(m.group(2))
        cue_text = " ".join(text_lines).strip()
        if cue_text:
            cues.append((start, end, cue_text))
    return cues


def load_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/SFNSDisplay.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/Library/Fonts/Arial.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def render_cue_png(text: str, font: ImageFont.FreeTypeFont, out_path: str) -> None:
    """Renderiza uma imagem RGBA 1080x1920 com a legenda no fundo."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Wrap se necessário
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        bbox = font.getbbox(test)
        if bbox[2] - bbox[0] > MAX_LINE_W and current:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)

    line_bboxes = [font.getbbox(l) for l in lines]
    line_heights = [bb[3] - bb[1] for bb in line_bboxes]
    total_h = sum(line_heights) + 4 * (len(lines) - 1)
    max_w = max(bb[2] - bb[0] for bb in line_bboxes)

    y0 = H - MARGIN_BOTTOM - total_h
    x0 = (W - max_w) // 2

    # Fundo semi-transparente
    draw.rectangle(
        [x0 - PAD, y0 - PAD, x0 + max_w + PAD, y0 + total_h + PAD],
        fill=(0, 0, 0, 180),
    )

    y = y0
    for line, bb, lh in zip(lines, line_bboxes, line_heights):
        lw = bb[2] - bb[0]
        x = (W - lw) // 2
        # Contorno preto
        for dx in range(-OUTLINE, OUTLINE + 1):
            for dy in range(-OUTLINE, OUTLINE + 1):
                if dx or dy:
                    draw.text((x + dx, y + dy), line, font=font, fill=(0, 0, 0, 255))
        # Texto branco
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
        y += lh + 4

    img.save(out_path, "PNG")


def generate_subtitle_video(
    srt_path: str, duration_s: float, out_path: str, fps: int = 24
) -> None:
    cues = parse_srt(srt_path)
    font = load_font(FONT_SIZE)

    with tempfile.TemporaryDirectory() as tmp:
        # Gera um PNG por cue único
        png_cache: dict[str, str] = {}
        for i, (_, _, text) in enumerate(cues):
            if text not in png_cache:
                p = os.path.join(tmp, f"cue_{i:04d}.png")
                render_cue_png(text, font, p)
                png_cache[text] = p

        # PNG transparente (silêncio / sem legenda)
        blank_path = os.path.join(tmp, "blank.png")
        Image.new("RGBA", (W, H), (0, 0, 0, 0)).save(blank_path, "PNG")

        # Monta timeline: (t_start, t_end, png_path)
        timeline: list[tuple[float, float, str]] = []
        prev = 0.0
        for start, end, text in sorted(cues, key=lambda c: c[0]):
            if start > prev + 0.001:
                timeline.append((prev, start, blank_path))
            timeline.append((start, end, png_cache[text]))
            prev = end
        if prev < duration_s:
            timeline.append((prev, duration_s, blank_path))

        # Concat list para ffmpeg
        concat_file = os.path.join(tmp, "concat.txt")
        with open(concat_file, "w") as f:
            for t_start, t_end, png_path in timeline:
                dur = max(1 / fps, t_end - t_start)
                f.write(f"file '{png_path}'\n")
                f.write(f"duration {dur:.4f}\n")
            # Último frame precisa ser repetido (bug concat demuxer)
            if timeline:
                f.write(f"file '{timeline[-1][2]}'\n")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", concat_file,
            "-vf", f"scale={W}:{H},format=rgba",
            "-r", str(fps),
            "-c:v", "libx264",
            "-pix_fmt", "yuva420p",
            "-preset", "fast",
            "-crf", "18",
            out_path,
        ]
        print(f"  gerando faixa de legendas → {Path(out_path).name}")
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            # Fallback: yuv420p se yuva420p não suportado
            cmd[cmd.index("yuva420p")] = "yuv420p"
            result2 = subprocess.run(cmd, capture_output=True)
            if result2.returncode != 0:
                print("AVISO: não foi possível gerar faixa de legendas:")
                print(result2.stderr.decode()[-500:])
                return
        print(f"  OK: {Path(out_path).name}")


if __name__ == "__main__":
    srt = sys.argv[1]
    dur = float(sys.argv[2])
    out = sys.argv[3]
    fps = int(sys.argv[4]) if len(sys.argv) > 4 else 24
    generate_subtitle_video(srt, dur, out, fps)
