from __future__ import annotations

from pathlib import Path

from app.server.session import default_session, load_session, pid_alive, reclaim_job, save_session


def test_roundtrip(tmp_path: Path):
    data = default_session(tmp_path)
    save_session(tmp_path, data)
    loaded = load_session(tmp_path)
    assert loaded["folder"] == str(tmp_path.resolve())
    assert loaded["job"]["kind"] == "idle"
    assert (tmp_path / "edit" / "app_session.json").exists()


def test_reclaim_dead_pid():
    data = default_session(Path("C:/footage"))
    data["job"] = {"kind": "render", "pid": 99999999, "started_at": "t", "output": "x", "log": "y"}
    out = reclaim_job(data)
    assert out["job"]["kind"] == "idle"
    assert out["job"]["pid"] is None


def test_reclaim_keeps_job_if_worker_pid_alive():
    import os
    data = default_session(Path("C:/footage"))
    data["job"] = {
        "kind": "claude",
        "pid": 99999999,
        "worker_pid": os.getpid(),
        "started_at": "t",
        "output": None,
        "log": None,
    }
    out = reclaim_job(data)
    assert out["job"]["kind"] == "claude"
    assert out.get("last_error") is None


def test_reclaim_keeps_live_pid():
    import os
    data = default_session(Path("C:/footage"))
    data["job"] = {"kind": "transcribe", "pid": os.getpid(), "started_at": "t", "output": None, "log": None}
    out = reclaim_job(data)
    assert out["job"]["kind"] == "transcribe"
    assert out["job"]["pid"] == os.getpid()


def test_pid_alive_false_for_none():
    assert pid_alive(None) is False


def test_pid_alive_true_for_self():
    import os
    assert pid_alive(os.getpid()) is True
