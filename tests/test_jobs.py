from __future__ import annotations

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
