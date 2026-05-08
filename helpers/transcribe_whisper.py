"""Local Whisper transcription, emits Scribe-compatible JSON.

Uses faster-whisper with word_timestamps=True. Synthesizes 'spacing'
entries from gaps so pack_transcripts.py works unchanged.

Output schema: {"words": [{type, text, start, end, speaker_id}]}
type ∈ {"word", "spacing"}
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from faster_whisper import WhisperModel


def extract_audio(video: Path, dest: Path) -> None:
    cmd = [
        "ffmpeg", "-y", "-i", str(video),
        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
        str(dest),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def transcribe(video: Path, edit_dir: Path, model_size: str, language: str | None) -> Path:
    transcripts_dir = edit_dir / "transcripts"
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    out_path = transcripts_dir / f"{video.stem}.json"
    if out_path.exists():
        print(f"cached: {out_path.name}")
        return out_path

    print(f"loading whisper model: {model_size}")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    with tempfile.TemporaryDirectory() as tmp:
        audio = Path(tmp) / f"{video.stem}.wav"
        print(f"  extracting audio from {video.name}")
        extract_audio(video, audio)
        print(f"  transcribing...")
        segments, info = model.transcribe(
            str(audio),
            language=language,
            word_timestamps=True,
            vad_filter=True,
        )
        words_out: list[dict] = []
        prev_end: float | None = None
        for seg in segments:
            if seg.words is None:
                continue
            for w in seg.words:
                if prev_end is not None and w.start - prev_end > 0.0:
                    words_out.append({
                        "type": "spacing",
                        "text": " ",
                        "start": prev_end,
                        "end": w.start,
                        "speaker_id": "speaker_0",
                    })
                words_out.append({
                    "type": "word",
                    "text": w.word.strip(),
                    "start": w.start,
                    "end": w.end,
                    "speaker_id": "speaker_0",
                })
                prev_end = w.end

        payload = {
            "language_code": info.language,
            "language_probability": info.language_probability,
            "words": words_out,
        }
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
        print(f"  saved: {out_path.name}  ({len([w for w in words_out if w['type']=='word'])} words)")
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    ap.add_argument("--edit-dir", type=Path, default=None)
    ap.add_argument("--model", default="medium", help="tiny|base|small|medium|large-v3")
    ap.add_argument("--language", default=None, help="ISO code, e.g. 'pt'. Omit to auto-detect.")
    args = ap.parse_args()

    video = args.video.resolve()
    if not video.exists():
        sys.exit(f"video not found: {video}")
    edit_dir = (args.edit_dir or (video.parent / "edit")).resolve()
    transcribe(video, edit_dir, args.model, args.language)


if __name__ == "__main__":
    main()
