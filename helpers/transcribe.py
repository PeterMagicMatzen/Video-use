"""Transcribe a video with Groq Whisper (free) or ElevenLabs Scribe.

Extracts mono 16kHz audio via ffmpeg, uploads it for word-level timestamps,
writes the response to <edit_dir>/transcripts/<video_stem>.json.

Providers:
  groq        whisper-large-v3-turbo. Free, fast, keeps fillers. No diarization,
              no audio events. 25 MB upload cap (~25 min of 16k mono FLAC).
  elevenlabs  Scribe. Paid. Adds diarization + audio events, no size cap worth
              worrying about. Required for multi-speaker footage.

Default is `auto`: Groq if GROQ_API_KEY resolves, otherwise ElevenLabs.

Cached: if the output file already exists, the upload is skipped.

Usage:
    python helpers/transcribe.py <video_path>
    python helpers/transcribe.py <video_path> --edit-dir /custom/edit
    python helpers/transcribe.py <video_path> --language en
    python helpers/transcribe.py <video_path> --num-speakers 2
    python helpers/transcribe.py <video_path> --provider elevenlabs
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests


SCRIBE_URL = "https://api.elevenlabs.io/v1/speech-to-text"
GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_MODEL = "whisper-large-v3-turbo"
GROQ_MAX_UPLOAD_MB = 25.0  # free tier; Groq's dev tier allows 100

PROVIDER_KEYS = {"groq": "GROQ_API_KEY", "elevenlabs": "ELEVENLABS_API_KEY"}


def _read_env_var(name: str) -> str:
    """Look up a var in the repo .env, the cwd .env, then the environment.

    Blank values are skipped, so a placeholder line like `ELEVENLABS_API_KEY=`
    in a freshly copied .env doesn't shadow a real key set elsewhere.
    """
    candidates = [
        Path(__file__).resolve().parent.parent / ".env",
        Path(".env"),
    ]
    for candidate in candidates:
        if candidate.exists():
            for line in candidate.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                if k.strip().removeprefix("export ").strip() == name:
                    v = v.strip().strip('"').strip("'")
                    if v:
                        return v
    return os.environ.get(name, "")


def load_provider_key(preferred: str = "auto") -> tuple[str, str]:
    """Resolve (provider, api_key). `preferred` is 'auto', 'groq' or 'elevenlabs'.

    'auto' prefers free Groq Whisper and falls back to ElevenLabs Scribe.
    """
    if preferred in PROVIDER_KEYS:
        key = _read_env_var(PROVIDER_KEYS[preferred])
        if not key:
            sys.exit(f"--provider {preferred} needs {PROVIDER_KEYS[preferred]} in .env or environment")
        return preferred, key

    for provider, env_name in PROVIDER_KEYS.items():
        key = _read_env_var(env_name)
        if key:
            return provider, key
    sys.exit("No transcription key: set GROQ_API_KEY (free) or ELEVENLABS_API_KEY in .env")


def resolve_provider(preferred: str, num_speakers: int | None) -> tuple[str, str]:
    """load_provider_key, but route diarization requests away from Groq."""
    if preferred == "auto" and num_speakers and _read_env_var("ELEVENLABS_API_KEY"):
        preferred = "elevenlabs"

    provider, api_key = load_provider_key(preferred)
    if num_speakers and provider == "groq":
        print(
            "warning: Groq Whisper has no diarization — --num-speakers ignored, "
            "no speaker_id in the transcript",
            file=sys.stderr,
        )
    return provider, api_key


def extract_audio(video_path: Path, dest: Path) -> None:
    """Mono 16 kHz audio. Codec follows the destination suffix — FLAC for Groq
    (lossless, smaller than WAV, and what Groq documents as the preferred
    upload format), plain WAV for Scribe."""
    codec = "flac" if dest.suffix == ".flac" else "pcm_s16le"
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vn", "-ac", "1", "-ar", "16000", "-c:a", codec,
        str(dest),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def call_scribe(
    audio_path: Path,
    api_key: str,
    language: str | None = None,
    num_speakers: int | None = None,
) -> dict:
    data: dict[str, str] = {
        "model_id": "scribe_v1",
        "diarize": "true",
        "tag_audio_events": "true",
        "timestamps_granularity": "word",
    }
    if language:
        data["language_code"] = language
    if num_speakers:
        data["num_speakers"] = str(num_speakers)

    with open(audio_path, "rb") as f:
        resp = requests.post(
            SCRIBE_URL,
            headers={"xi-api-key": api_key},
            files={"file": (audio_path.name, f, "audio/wav")},
            data=data,
            timeout=1800,
        )

    if resp.status_code != 200:
        raise RuntimeError(f"Scribe returned {resp.status_code}: {resp.text[:500]}")

    return resp.json()


def _normalize_groq_words(raw_words: list[dict]) -> list[dict]:
    """Map Whisper words onto the Scribe entry shape the rest of video-use reads:
    {text, start, end, type, speaker_id}.

    Whisper timestamps occasionally run backwards (a word starting before the
    previous one ended). Cuts snap to these boundaries, so clamp the sequence
    monotonic rather than let a negative span reach the EDL. Real silences are
    untouched — clamping only moves a start that was already behind.
    """
    words: list[dict] = []
    prev_end = 0.0
    for w in raw_words:
        text = (w.get("word") or "").strip()
        if not text:
            continue
        start = max(float(w.get("start", prev_end)), prev_end)
        end = max(float(w.get("end", start)), start)
        words.append({
            "text": text,
            "start": start,
            "end": end,
            "type": "word",
            "speaker_id": None,
        })
        prev_end = end
    return words


def call_groq(
    audio_path: Path,
    api_key: str,
    language: str | None = None,
) -> dict:
    """Free Whisper transcription via Groq. Returns the Scribe payload shape.

    No diarization and no audio events — fine for single-speaker footage, but
    multi-speaker work wants ElevenLabs.
    """
    size_mb = audio_path.stat().st_size / (1024 * 1024)
    if size_mb > GROQ_MAX_UPLOAD_MB:
        raise RuntimeError(
            f"{audio_path.stem}: {size_mb:.1f} MB of audio exceeds Groq's "
            f"{GROQ_MAX_UPLOAD_MB:.0f} MB upload cap. Use --provider elevenlabs, "
            f"or split the source into shorter takes."
        )

    data: dict[str, str] = {
        "model": GROQ_MODEL,
        "response_format": "verbose_json",
        "timestamp_granularities[]": "word",
    }
    if language:
        data["language"] = language

    with open(audio_path, "rb") as f:
        resp = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": (audio_path.name, f, "audio/flac")},
            data=data,
            timeout=1800,
        )

    if resp.status_code != 200:
        raise RuntimeError(f"Groq returned {resp.status_code}: {resp.text[:500]}")

    raw = resp.json()
    return {
        "language_code": raw.get("language", language or ""),
        "text": raw.get("text", ""),
        "words": _normalize_groq_words(raw.get("words", [])),
    }


def transcribe_one(
    video: Path,
    edit_dir: Path,
    api_key: str,
    language: str | None = None,
    num_speakers: int | None = None,
    verbose: bool = True,
    provider: str = "groq",
) -> Path:
    """Transcribe a single video. Returns path to transcript JSON.

    Cached: returns existing path immediately if the transcript already exists.
    """
    transcripts_dir = edit_dir / "transcripts"
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    out_path = transcripts_dir / f"{video.stem}.json"

    if out_path.exists():
        if verbose:
            print(f"cached: {out_path.name}")
        return out_path

    if verbose:
        print(f"  extracting audio from {video.name}", flush=True)

    t0 = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        suffix = ".flac" if provider == "groq" else ".wav"
        audio = Path(tmp) / f"{video.stem}{suffix}"
        extract_audio(video, audio)
        size_mb = audio.stat().st_size / (1024 * 1024)
        if verbose:
            print(f"  uploading {audio.name} ({size_mb:.1f} MB) to {provider}", flush=True)
        if provider == "groq":
            payload = call_groq(audio, api_key, language)
        else:
            payload = call_scribe(audio, api_key, language, num_speakers)

    out_path.write_text(json.dumps(payload, indent=2))
    dt = time.time() - t0

    if verbose:
        kb = out_path.stat().st_size / 1024
        print(f"  saved: {out_path.name} ({kb:.1f} KB) in {dt:.1f}s")
        if isinstance(payload, dict) and "words" in payload:
            print(f"    words: {len(payload['words'])}")

    return out_path


def main() -> None:
    ap = argparse.ArgumentParser(description="Transcribe a video with Groq Whisper or ElevenLabs Scribe")
    ap.add_argument("video", type=Path, help="Path to video file")
    ap.add_argument(
        "--edit-dir",
        type=Path,
        default=None,
        help="Edit output directory (default: <video_parent>/edit)",
    )
    ap.add_argument(
        "--language",
        type=str,
        default=None,
        help="Optional ISO language code (e.g., 'en'). Omit to auto-detect.",
    )
    ap.add_argument(
        "--num-speakers",
        type=int,
        default=None,
        help="Optional number of speakers when known. Improves diarization accuracy (ElevenLabs only).",
    )
    ap.add_argument(
        "--provider",
        choices=["auto", "groq", "elevenlabs"],
        default="auto",
        help="Transcription backend. Default auto: free Groq Whisper, else ElevenLabs Scribe.",
    )
    args = ap.parse_args()

    video = args.video.resolve()
    if not video.exists():
        sys.exit(f"video not found: {video}")

    edit_dir = (args.edit_dir or (video.parent / "edit")).resolve()
    provider, api_key = resolve_provider(args.provider, args.num_speakers)

    transcribe_one(
        video=video,
        edit_dir=edit_dir,
        api_key=api_key,
        language=args.language,
        num_speakers=args.num_speakers,
        provider=provider,
    )


if __name__ == "__main__":
    main()
