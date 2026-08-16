from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import pytest

from app.server.jobs import start_transcribe, start_render
from app.server.session import load_session, save_session, default_session


def test_start_transcribe_rejects_busy(tmp_path: Path):
    (tmp_path / "edit").mkdir()
    s = default_session(tmp_path)
    s["job"]["kind"] = "render"
    s["job"]["pid"] = 1
    save_session(tmp_path, s)
    with pytest.raises(RuntimeError, match="busy"):
        start_transcribe(tmp_path)


def test_start_render_rejects_invalid_edl(tmp_path: Path, monkeypatch):
    (tmp_path / "a.mp4").write_bytes(b"x")
    edit = tmp_path / "edit"
    edit.mkdir()
    (edit / "edl.json").write_text('{"sources":{},"ranges":[]}', encoding="utf-8")
    save_session(tmp_path, default_session(tmp_path))
    called = {"n": 0}
    from app.server import proc as proc_mod
    monkeypatch.setattr(proc_mod, "run_helper", lambda *a, **k: called.__setitem__("n", called["n"] + 1))
    with pytest.raises(RuntimeError, match="invalid"):
        start_render(tmp_path, preview=True)
    assert called["n"] == 0


def test_failed_preview_render_keeps_last_good_file(tmp_path: Path, monkeypatch):
    src = tmp_path / "a.mp4"
    src.write_bytes(b"x")
    edit = tmp_path / "edit"
    edit.mkdir()
    edl = {
        "version": 1,
        "sources": {"A": str(src)},
        "ranges": [{"source": "A", "start": 0, "end": 1.0, "beat": "HOOK", "quote": "x", "reason": "y"}],
        "grade": "none",
        "overlays": [],
        "total_duration_s": 1.0,
    }
    (edit / "edl.json").write_text(json.dumps(edl), encoding="utf-8")
    preview = edit / "preview.mp4"
    original = b"LAST-GOOD-PREVIEW"
    preview.write_bytes(original)
    save_session(tmp_path, default_session(tmp_path))

    def fake_run_helper(script, args, *, cwd=None):
        o_idx = args.index("-o")
        out = Path(cwd or ".") / args[o_idx + 1]
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"TRUNCATED-GARBAGE")
        return subprocess.CompletedProcess(
            args=["python", script, *args],
            returncode=1,
            stdout="",
            stderr="ffmpeg exploded\n" + "\n".join(f"line {i}" for i in range(50)),
        )

    from app.server import jobs as jobs_mod
    from app.server import proc as proc_mod
    monkeypatch.setattr(proc_mod, "run_helper", fake_run_helper)
    monkeypatch.setattr(jobs_mod, "spawn_job", lambda kind, folder: jobs_mod.run_render_sync(folder, preview=kind == "render-preview") or 1)
    start_render(tmp_path, preview=True)

    deadline = time.time() + 5
    while time.time() < deadline:
        s = load_session(tmp_path)
        if (s.get("job") or {}).get("kind") in (None, "idle"):
            break
        time.sleep(0.05)
    else:
        pytest.fail("render job did not become idle")

    assert preview.read_bytes() == original
