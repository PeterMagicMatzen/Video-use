import json
import re
import subprocess
from pathlib import Path

HDR_TRANSFERS = {"smpte2084", "arib-std-b67"}
TONEMAP_CHAIN = (
    "zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,"
    "tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p"
)
PUNCT_BREAK = set(".,!?;:")

CAPTION_STYLES = {
    "bold": {
        "uppercase": True,
        "force_style": (
            "FontName=Arial,FontSize=18,Bold=1,PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,Alignment=2,MarginV=90"
        ),
    },
    "neon": {
        "uppercase": True,
        "force_style": (
            "FontName=Arial,FontSize=18,Bold=1,PrimaryColour=&H0000FFD4,"
            "OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,Alignment=2,MarginV=90"
        ),
    },
    "boxed": {
        "uppercase": True,
        "force_style": (
            "FontName=Arial,FontSize=17,Bold=1,PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00000000,BorderStyle=3,Outline=1,Shadow=0,Alignment=2,MarginV=90"
        ),
    },
    "minimal": {
        "uppercase": False,
        "force_style": (
            "FontName=Arial,FontSize=14,Bold=0,PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00000000,BorderStyle=1,Outline=1,Shadow=0,Alignment=2,MarginV=90"
        ),
    },
}


def _run(cmd: list) -> None:
    proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", "replace")
        raise RuntimeError(f"ffmpeg failed: {err[-800:]}")


def probe(video: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,color_transfer:format=duration",
         "-of", "json", str(video)],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(out.stdout)
    stream = (data.get("streams") or [{}])[0]
    return {
        "width": int(stream.get("width") or 0),
        "height": int(stream.get("height") or 0),
        "duration": float((data.get("format") or {}).get("duration") or 0),
        "hdr": stream.get("color_transfer") in HDR_TRANSFERS,
    }


def extract_segment(source: Path, start: float, end: float, out_path: Path, info: dict) -> None:
    duration = end - start
    portrait = info["height"] > info["width"]
    scale = "scale=-2:min(1920\\,ih)" if portrait else "scale=min(1920\\,iw):-2"
    vf_parts = []
    if info["hdr"]:
        vf_parts.append(TONEMAP_CHAIN)
    vf_parts.append(scale)
    fade_out = max(0.0, duration - 0.03)
    af = f"afade=t=in:st=0:d=0.03,afade=t=out:st={fade_out:.3f}:d=0.03"
    _run([
        "ffmpeg", "-y", "-ss", f"{start:.3f}", "-i", str(source), "-t", f"{duration:.3f}",
        "-vf", ",".join(vf_parts), "-af", af,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", "24",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart", str(out_path),
    ])


def concat_segments(paths: list, out_path: Path, work_dir: Path) -> None:
    concat_list = work_dir / "_concat.txt"
    concat_list.write_text("".join(f"file '{p.resolve()}'\n" for p in paths))
    _run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-c", "copy", "-movflags", "+faststart", str(out_path),
    ])
    concat_list.unlink(missing_ok=True)


def _srt_ts(seconds: float) -> str:
    total_ms = int(round(seconds * 1000))
    h, rem = divmod(total_ms, 3600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt(words: list, ranges: list, out_path: Path, uppercase: bool, max_words: int = 3) -> int:
    entries = []
    offset = 0.0
    items = [w for w in words if w.get("type") == "word" and w.get("start") is not None]
    for r_start, r_end in ranges:
        in_range = [w for w in items if w["end"] > r_start and w["start"] < r_end]
        chunks, current = [], []
        for w in in_range:
            text = (w.get("text") or "").strip()
            if not text:
                continue
            current.append(w)
            if len(current) >= max_words or text[-1] in PUNCT_BREAK:
                chunks.append(current)
                current = []
        if current:
            chunks.append(current)
        for chunk in chunks:
            a = max(r_start, chunk[0]["start"]) - r_start + offset
            b = min(r_end, chunk[-1]["end"]) - r_start + offset
            if b <= a:
                b = a + 0.4
            text = re.sub(r"\s+", " ", " ".join((w.get("text") or "").strip() for w in chunk)).strip()
            text = text.rstrip(",;:")
            if uppercase:
                text = text.upper()
            entries.append((a, b, text))
        offset += r_end - r_start
    entries.sort(key=lambda e: e[0])
    lines = []
    for i, (a, b, t) in enumerate(entries, start=1):
        lines += [str(i), f"{_srt_ts(a)} --> {_srt_ts(b)}", t, ""]
    out_path.write_text("\n".join(lines))
    return len(entries)


def _escape_sub_path(path: Path) -> str:
    s = str(path.resolve()).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
    return s


def burn_captions(base: Path, srt: Path, force_style: str, out_path: Path) -> None:
    vf = f"subtitles='{_escape_sub_path(srt)}':force_style='{force_style}'"
    _run([
        "ffmpeg", "-y", "-i", str(base), "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "copy", "-movflags", "+faststart", str(out_path),
    ])


def loudnorm(input_path: Path, out_path: Path) -> None:
    _run([
        "ffmpeg", "-y", "-i", str(input_path), "-c:v", "copy",
        "-af", "loudnorm=I=-14:TP=-1:LRA=11",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart", str(out_path),
    ])


def render_export(source: Path, words: list, ranges: list, style_key: str,
                  burn: bool, work_dir: Path, out_path: Path, progress_cb=None) -> None:
    work_dir.mkdir(parents=True, exist_ok=True)
    info = probe(source)
    style = CAPTION_STYLES.get(style_key, CAPTION_STYLES["bold"])

    seg_paths = []
    total = len(ranges)
    for i, (a, b) in enumerate(ranges):
        seg = work_dir / f"seg_{i:03d}.mp4"
        extract_segment(source, a, b, seg, info)
        seg_paths.append(seg)
        if progress_cb:
            progress_cb(int(5 + 60 * (i + 1) / total))

    base = work_dir / "base.mp4"
    concat_segments(seg_paths, base, work_dir)
    if progress_cb:
        progress_cb(70)

    if burn:
        srt = work_dir / "captions.srt"
        n = build_srt(words, ranges, srt, uppercase=style["uppercase"])
        if n > 0:
            captioned = work_dir / "captioned.mp4"
            burn_captions(base, srt, style["force_style"], captioned)
            base = captioned
    if progress_cb:
        progress_cb(88)

    loudnorm(base, out_path)
    if progress_cb:
        progress_cb(100)

    for p in seg_paths:
        p.unlink(missing_ok=True)
