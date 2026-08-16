from __future__ import annotations

from pathlib import Path

import pytest

from app.server.jobs import start_transcribe
from app.server.session import load_session, save_session, default_session


def test_start_transcribe_rejects_busy(tmp_path: Path):
    (tmp_path / "edit").mkdir()
    s = default_session(tmp_path)
    s["job"]["kind"] = "render"
    s["job"]["pid"] = 1
    save_session(tmp_path, s)
    with pytest.raises(RuntimeError, match="busy"):
        start_transcribe(tmp_path)
