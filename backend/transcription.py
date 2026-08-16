import os
import subprocess
import tempfile
from pathlib import Path

import requests

SCRIBE_URL = "https://api.elevenlabs.io/v1/speech-to-text"


def extract_audio(video_path: Path, dest: Path) -> None:
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
        str(dest),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def transcribe_video(video_path: Path) -> dict:
    api_key = os.environ["ELEVENLABS_API_KEY"]
    with tempfile.TemporaryDirectory() as tmp:
        audio = Path(tmp) / "audio.wav"
        extract_audio(video_path, audio)
        data = {
            "model_id": "scribe_v1",
            "tag_audio_events": "false",
            "timestamps_granularity": "word",
        }
        with open(audio, "rb") as f:
            resp = requests.post(
                SCRIBE_URL,
                headers={"xi-api-key": api_key},
                files={"file": ("audio.wav", f, "audio/wav")},
                data=data,
                timeout=1800,
            )
    if resp.status_code != 200:
        raise RuntimeError(f"Scribe returned {resp.status_code}: {resp.text[:500]}")
    return resp.json()
