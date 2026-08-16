from __future__ import annotations

from pathlib import Path

from app.server.session import default_session
from app.server.state import derive_center_state


def _folder(tmp: Path, videos=True, packed=False, edl=False, preview=False) -> Path:
    if videos:
        (tmp / "a.mp4").write_bytes(b"x")
    edit = tmp / "edit"
    edit.mkdir(exist_ok=True)
    if packed:
        (edit / "takes_packed.md").write_text("x", encoding="utf-8")
    if edl:
        (edit / "edl.json").write_text("{}", encoding="utf-8")
    if preview:
        (edit / "preview.mp4").write_bytes(b"x")
    return tmp


def test_empty(tmp_path: Path):
    assert derive_center_state(tmp_path, default_session(tmp_path)) == "empty"


def test_inventory(tmp_path: Path):
    _folder(tmp_path)
    assert derive_center_state(tmp_path, default_session(tmp_path)) == "inventory"


def test_transcribing(tmp_path: Path):
    _folder(tmp_path)
    s = default_session(tmp_path)
    s["job"]["kind"] = "transcribe"
    s["job"]["pid"] = 1
    assert derive_center_state(tmp_path, s) == "transcribing"


def test_packed(tmp_path: Path):
    _folder(tmp_path, packed=True)
    assert derive_center_state(tmp_path, default_session(tmp_path)) == "packed"


def test_error_after_pack(tmp_path: Path):
    _folder(tmp_path, packed=True)
    s = default_session(tmp_path)
    s["last_error"] = "Scribe returned 401"
    assert derive_center_state(tmp_path, s) == "error"


def test_strategy_ready(tmp_path: Path):
    _folder(tmp_path, packed=True, edl=True)
    s = default_session(tmp_path)
    s["edl_mtime_at_approve"] = (tmp_path / "edit" / "edl.json").stat().st_mtime
    s["chat_after_approve"] = False
    assert derive_center_state(tmp_path, s) == "strategy-ready"


def test_stale_after_chat(tmp_path: Path):
    _folder(tmp_path, packed=True, edl=True, preview=True)
    s = default_session(tmp_path)
    s["edl_mtime_at_approve"] = (tmp_path / "edit" / "edl.json").stat().st_mtime
    s["chat_after_approve"] = True
    assert derive_center_state(tmp_path, s) == "stale"


def test_preview_ready(tmp_path: Path):
    _folder(tmp_path, packed=True, edl=True, preview=True)
    s = default_session(tmp_path)
    s["edl_mtime_at_approve"] = (tmp_path / "edit" / "edl.json").stat().st_mtime
    s["chat_after_approve"] = False
    assert derive_center_state(tmp_path, s) == "preview-ready"
