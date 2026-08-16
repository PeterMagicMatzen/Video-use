from __future__ import annotations

import json
from pathlib import Path

from app.server.inventory import VIDEO_EXTS, find_videos, probe_source
from app.server.proc import helper_env
from app.server.recents import add_recent, load_recents


def test_find_videos_filters(tmp_path: Path):
    (tmp_path / "a.MP4").write_bytes(b"x")
    (tmp_path / "b.webm").write_bytes(b"x")
    (tmp_path / "note.txt").write_bytes(b"x")
    (tmp_path / "edit").mkdir()
    names = {p.name for p in find_videos(tmp_path)}
    assert names == {"a.MP4", "b.webm"}
    assert ".webm" in VIDEO_EXTS


def test_helper_env_forces_utf8(monkeypatch):
    monkeypatch.setenv("FOO", "1")
    env = helper_env()
    assert env["PYTHONIOENCODING"] == "utf-8"
    assert env["PYTHONUTF8"] == "1"
    assert env["FOO"] == "1"


def test_probe_parses_ffprobe():
    payload = {
        "format": {"duration": "12.5"},
        "streams": [
            {"codec_type": "audio"},
            {"codec_type": "video", "width": 1920, "height": 1080, "avg_frame_rate": "30000/1001"},
        ],
    }
    def run(cmd, **kwargs):
        class R:
            returncode = 0
            stdout = json.dumps(payload)
            stderr = ""
        return R()
    info = probe_source(Path("C:/a.mp4"), run=run)
    assert info["duration_s"] == 12.5
    assert info["width"] == 1920
    assert info["height"] == 1080
    assert info["error"] is None


def test_recents_cap_and_dedupe(tmp_path, monkeypatch):
    from app.server import recents as recents_mod
    monkeypatch.setattr(recents_mod, "RECENTS_PATH", tmp_path / "recents.json")
    for i in range(12):
        add_recent(Path(f"C:/f/{i}"))
    add_recent(Path("C:/f/11"))
    items = load_recents()
    assert items[0].endswith("11")
    assert len(items) == 10
