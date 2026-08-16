"""Transparent overlay clips for talking-head packages (hook, lower-third, keywords, end)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


W, H = 1080, 1920


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _new_canvas() -> Image.Image:
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))


def _save_clip(png: Path, dest: Path, duration: float) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(png),
        "-t", f"{duration:.2f}",
        "-r", "30",
        "-c:v", "qtrle",
        "-pix_fmt", "argb",
        str(dest),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", str(png),
            "-t", f"{duration:.2f}",
            "-r", "30",
            "-c:v", "png",
            "-pix_fmt", "rgba",
            str(dest.with_suffix(".mov")),
        ]
        dest = dest.with_suffix(".mov")
        subprocess.run(cmd, check=True, capture_output=True)
    return dest


def _draw_hook(text: str) -> Image.Image:
    im = _new_canvas()
    draw = ImageDraw.Draw(im)
    font = _font(64)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (W - tw) // 2
    y = int(H * 0.18)
    pad = 28
    draw.rounded_rectangle(
        (x - pad, y - pad, x + tw + pad, y + th + pad),
        radius=18,
        fill=(8, 8, 8, 200),
    )
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))
    return im


def _draw_lower_third(name: str, label: str) -> Image.Image:
    im = _new_canvas()
    draw = ImageDraw.Draw(im)
    bar_top = int(H * 0.72)
    draw.rectangle((0, bar_top, W, bar_top + 220), fill=(8, 8, 8, 210))
    draw.rectangle((0, bar_top, 14, bar_top + 220), fill=(255, 255, 255, 255))
    draw.text((48, bar_top + 36), name.upper(), font=_font(56), fill=(255, 255, 255, 255))
    draw.text((48, bar_top + 120), label.upper(), font=_font(28, bold=False), fill=(200, 200, 200, 255))
    return im


def _draw_keyword(word: str) -> Image.Image:
    im = _new_canvas()
    draw = ImageDraw.Draw(im)
    font = _font(72)
    bbox = draw.textbbox((0, 0), word, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (W - tw) // 2
    y = int(H * 0.38)
    pad_x, pad_y = 40, 24
    draw.rounded_rectangle(
        (x - pad_x, y - pad_y, x + tw + pad_x, y + th + pad_y),
        radius=12,
        fill=(8, 8, 8, 190),
    )
    draw.text((x, y), word, font=font, fill=(255, 255, 255, 255))
    return im


def _draw_end() -> Image.Image:
    im = Image.new("RGBA", (W, H), (8, 8, 8, 230))
    draw = ImageDraw.Draw(im)
    line = "FOLLOW FOR MORE"
    font = _font(56)
    bbox = draw.textbbox((0, 0), line, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, int(H * 0.46)), line, font=font, fill=(255, 255, 255, 255))
    return im


def build_talking_head_graphics(
    *,
    edit_dir: Path,
    speaker: str,
    hook: str,
    keywords: list[tuple[float, str]],
    output_duration: float,
) -> list[dict]:
    slot = edit_dir / "animations" / "talking_head"
    slot.mkdir(parents=True, exist_ok=True)
    overlays: list[dict] = []

    hook_png = slot / "hook.png"
    _draw_hook(hook[:42]).save(hook_png)
    hook_clip = _save_clip(hook_png, slot / "hook.mov", 2.8)
    overlays.append({"file": str(hook_clip), "start_in_output": 0.0, "duration": 2.8})

    lt_png = slot / "lower.png"
    _draw_lower_third(speaker, "talking head").save(lt_png)
    lt_clip = _save_clip(lt_png, slot / "lower.mov", 3.6)
    overlays.append({"file": str(lt_clip), "start_in_output": 0.4, "duration": 3.6})

    t = 6.0
    for i, (_src_t, word) in enumerate(keywords[:2]):
        png = slot / f"key_{i}.png"
        _draw_keyword(word[:18]).save(png)
        clip = _save_clip(png, slot / f"key_{i}.mov", 2.2)
        start = min(max(t, 5.0), max(0.0, output_duration - 3.0))
        overlays.append({"file": str(clip), "start_in_output": round(start, 2), "duration": 2.2})
        t = start + 3.2

    end_png = slot / "end.png"
    _draw_end().save(end_png)
    end_dur = 1.6
    end_start = max(0.0, output_duration - end_dur)
    end_clip = _save_clip(end_png, slot / "end.mov", end_dur)
    overlays.append({"file": str(end_clip), "start_in_output": round(end_start, 2), "duration": end_dur})
    return overlays
