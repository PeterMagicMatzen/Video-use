"""Transparent overlay clips — Caption-style, no generic 'talking head' stamp."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


W, H = 1080, 1920


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _new_canvas() -> Image.Image:
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))


def _wrap(text: str, font: ImageFont.ImageFont, max_w: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    cur = words[0]
    draw = ImageDraw.Draw(_new_canvas())
    for word in words[1:]:
        trial = f"{cur} {word}"
        if draw.textbbox((0, 0), trial, font=font)[2] <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    lines.append(cur)
    return lines[:2]


def _text_with_shadow(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font, fill, shadow=(0, 0, 0, 160)):
    x, y = xy
    draw.text((x + 2, y + 2), text, font=font, fill=shadow)
    draw.text((x, y), text, font=font, fill=fill)


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
    from hidden_proc import run as hidden_run
    proc = hidden_run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        dest = dest.with_suffix(".mov")
        hidden_run(
            [
                "ffmpeg", "-y",
                "-loop", "1", "-i", str(png),
                "-t", f"{duration:.2f}",
                "-r", "30",
                "-c:v", "png",
                "-pix_fmt", "rgba",
                str(dest),
            ],
            check=True,
            capture_output=True,
        )
    return dest


def _draw_hook(text: str) -> Image.Image:
    im = _new_canvas()
    draw = ImageDraw.Draw(im)
    font = _font(54)
    lines = _wrap(text.upper(), font, W - 160)
    if not lines:
        return im
    y = int(H * 0.14)
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = (W - tw) // 2
        # thin pill, not a billboard
        pad_x, pad_y = 22, 12
        draw.rounded_rectangle(
            (x - pad_x, y - pad_y, x + tw + pad_x, y + th + pad_y),
            radius=999,
            fill=(8, 8, 10, 150),
        )
        _text_with_shadow(draw, (x, y), line, font, (255, 255, 255, 255))
        y += th + 22
    return im


def _draw_lower_third(name: str, label: str | None) -> Image.Image:
    im = _new_canvas()
    draw = ImageDraw.Draw(im)
    name_font = _font(40)
    label_font = _font(22, bold=False)
    name_bb = draw.textbbox((0, 0), name, font=name_font)
    nw = name_bb[2] - name_bb[0]
    bar_h = 96 if label else 72
    bar_w = min(W - 80, max(280, nw + 80))
    left, top = 40, int(H * 0.78)
    draw.rounded_rectangle((left, top, left + bar_w, top + bar_h), radius=14, fill=(10, 10, 12, 165))
    draw.rectangle((left, top + 16, left + 6, top + bar_h - 16), fill=(243, 234, 210, 255))
    draw.text((left + 24, top + 12), name, font=name_font, fill=(255, 255, 255, 255))
    if label:
        draw.text((left + 24, top + 54), label, font=label_font, fill=(200, 196, 186, 255))
    return im


def _draw_keyword(word: str) -> Image.Image:
    im = _new_canvas()
    draw = ImageDraw.Draw(im)
    font = _font(48)
    word = word.upper()
    bbox = draw.textbbox((0, 0), word, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (W - tw) // 2
    y = int(H * 0.22)
    pad_x, pad_y = 28, 14
    draw.rounded_rectangle(
        (x - pad_x, y - pad_y, x + tw + pad_x, y + th + pad_y),
        radius=999,
        fill=(8, 8, 10, 155),
    )
    _text_with_shadow(draw, (x, y), word, font, (255, 252, 245, 255))
    return im


def _draw_end(line: str) -> Image.Image:
    im = _new_canvas()
    draw = ImageDraw.Draw(im)
    font = _font(44)
    line = line.upper()
    bbox = draw.textbbox((0, 0), line, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (W - tw) // 2
    y = int(H * 0.82)
    draw.rounded_rectangle((x - 24, y - 12, x + tw + 24, y + th + 12), radius=999, fill=(8, 8, 10, 150))
    _text_with_shadow(draw, (x, y), line, font, (255, 255, 255, 255))
    return im


def build_talking_head_graphics(
    *,
    edit_dir: Path,
    speaker: str | None,
    hook: str,
    keywords: list[tuple[float, str]],
    output_duration: float,
    role: str | None = None,
    end: str = "",
) -> list[dict]:
    slot = edit_dir / "animations" / "talking_head"
    slot.mkdir(parents=True, exist_ok=True)
    overlays: list[dict] = []

    hook = (hook or "").strip()
    if hook and hook.upper() not in {"WATCH THIS", "TALKING HEAD", "SPEAKER"}:
        hook_png = slot / "hook.png"
        _draw_hook(hook[:42]).save(hook_png)
        hook_clip = _save_clip(hook_png, slot / "hook.mov", 2.1)
        overlays.append({"file": str(hook_clip), "start_in_output": 0.12, "duration": 2.1})

    name = (speaker or "").strip()
    role_clean = (role or "").strip()
    if name and name.upper() not in {"SPEAKER", "HOST"}:
        lt_png = slot / "lower.png"
        _draw_lower_third(name, role_clean or None).save(lt_png)
        lt_clip = _save_clip(lt_png, slot / "lower.mov", 2.4)
        overlays.append({"file": str(lt_clip), "start_in_output": 0.55, "duration": 2.4})

    used = {hook.upper()} if hook else set()
    t = 3.4
    for i, (src_t, word) in enumerate(keywords[:3]):
        label = (word or "").strip()
        if not label or label.upper() in used or label.upper() in {"TALKING HEAD", "SPEAKER"}:
            continue
        used.add(label.upper())
        png = slot / f"key_{i}.png"
        _draw_keyword(label[:18]).save(png)
        clip = _save_clip(png, slot / f"key_{i}.mov", 1.7)
        start = float(src_t) if src_t and src_t > 0.4 else t
        start = min(max(start, 2.4), max(0.4, output_duration - 2.2))
        overlays.append({"file": str(clip), "start_in_output": round(start, 2), "duration": 1.7})
        t = start + 2.4

    end_line = (end or "").strip()
    if end_line and end_line.upper() not in {"FOLLOW FOR MORE", "FOLLOW", "SUBSCRIBE"}:
        end_png = slot / "end.png"
        _draw_end(end_line).save(end_png)
        end_dur = 1.4
        end_start = max(0.4, output_duration - end_dur)
        end_clip = _save_clip(end_png, slot / "end.mov", end_dur)
        overlays.append({"file": str(end_clip), "start_in_output": round(end_start, 2), "duration": end_dur})
    return overlays
