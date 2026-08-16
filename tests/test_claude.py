from __future__ import annotations

from pathlib import Path

import pytest

from app.server.claude import claude_cmd, parse_session_id, EDITOR_BRIEF
from app.server.paths import REPO_ROOT


def test_first_turn_has_no_resume(tmp_path: Path):
    cmd = claude_cmd(folder=tmp_path, session_id=None, prompt="hello")
    assert cmd[0] == "claude"
    assert "-p" in cmd
    assert "--continue" not in cmd
    assert "--resume" not in cmd
    assert "--dangerously-skip-permissions" not in cmd
    assert "--permission-mode" in cmd
    assert cmd[cmd.index("--permission-mode") + 1] == "acceptEdits"
    assert "--output-format" in cmd
    assert "stream-json" in cmd
    assert "--allowedTools" in cmd
    assert "Bash" in " ".join(cmd)
    # Bash is disallowed
    dis = cmd.index("--disallowedTools")
    assert "Bash" in cmd[dis + 1]
    assert str(tmp_path) in cmd
    assert str(REPO_ROOT) in cmd
    assert any(EDITOR_BRIEF[:20] in a for a in cmd) or "--append-system-prompt" in cmd


def test_later_turn_resumes(tmp_path: Path):
    cmd = claude_cmd(folder=tmp_path, session_id="abc-123", prompt="more")
    assert "--resume" in cmd
    assert "abc-123" in cmd
    assert "--continue" not in cmd


def test_parse_session_id():
    assert parse_session_id('{"type":"system","subtype":"init","session_id":"sid-1"}') == "sid-1"
    assert parse_session_id("not-json") is None
