from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.server.main import app, reset_current_folder


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    reset_current_folder()
    from app.server import recents as recents_mod
    monkeypatch.setattr(recents_mod, "RECENTS_PATH", tmp_path / "recents.json")
    return TestClient(app)


def test_doctor(client: TestClient):
    r = client.get("/api/doctor")
    assert r.status_code == 200
    body = r.json()
    assert "ok" in body
    assert "checks" in body
    assert all("sk-" not in c.get("detail", "") for c in body["checks"])


def test_state_without_folder(client: TestClient):
    assert client.get("/api/state").status_code == 404


def test_open_folder_lists_sources(client: TestClient, tmp_path: Path):
    (tmp_path / "take.mp4").write_bytes(b"x")
    r = client.post("/api/folder", json={"path": str(tmp_path)})
    assert r.status_code == 200
    body = r.json()
    assert body["center_state"] in {"inventory", "empty", "error"}
    assert any(s["name"] == "take.mp4" for s in body["sources"])
    assert (tmp_path / "edit").is_dir()
    assert body["chat_enabled"] is False


def test_no_transcribe_route_implied(client: TestClient, tmp_path: Path):
    (tmp_path / "take.mp4").write_bytes(b"x")
    client.post("/api/folder", json={"path": str(tmp_path)})
    # Opening a folder must not create takes_packed.md
    assert not (tmp_path / "edit" / "takes_packed.md").exists()


def test_transcribe_requires_explicit_click(client: TestClient, tmp_path: Path, monkeypatch):
    (tmp_path / "take.mp4").write_bytes(b"x")
    client.post("/api/folder", json={"path": str(tmp_path)})
    called = {"n": 0}
    from app.server import jobs as jobs_mod
    def fake_start(folder):
        called["n"] += 1
        return {"accepted": True}
    monkeypatch.setattr(jobs_mod, "start_transcribe", fake_start)
    # re-import routes use the name bound in main — patch app.server.main.start_transcribe
    import app.server.main as main_mod
    monkeypatch.setattr(main_mod, "start_transcribe", fake_start)
    r = client.post("/api/transcribe")
    assert r.status_code == 202
    assert called["n"] == 1


def test_transcribe_409_when_busy(client: TestClient, tmp_path: Path):
    (tmp_path / "take.mp4").write_bytes(b"x")
    client.post("/api/folder", json={"path": str(tmp_path)})
    from app.server.session import load_session, save_session
    s = load_session(tmp_path)
    s["job"]["kind"] = "transcribe"
    s["job"]["pid"] = 1
    save_session(tmp_path, s)
    r = client.post("/api/transcribe")
    assert r.status_code == 409


def test_approve_route_exists(client: TestClient, tmp_path: Path, monkeypatch):
    (tmp_path / "take.mp4").write_bytes(b"x")
    (tmp_path / "edit").mkdir()
    (tmp_path / "edit" / "takes_packed.md").write_text("x", encoding="utf-8")
    client.post("/api/folder", json={"path": str(tmp_path)})
    import app.server.main as main_mod
    monkeypatch.setattr(main_mod, "start_approve_and_preview", lambda folder: {"accepted": True})
    r = client.post("/api/approve")
    assert r.status_code == 202


def test_preview_mtime_in_state(client: TestClient, tmp_path: Path):
    (tmp_path / "take.mp4").write_bytes(b"x")
    client.post("/api/folder", json={"path": str(tmp_path)})
    assert client.get("/api/state").json()["preview_mtime"] is None
    (tmp_path / "edit" / "preview.mp4").write_bytes(b"mp4")
    body = client.get("/api/state").json()
    assert body["has_preview"] is True
    assert isinstance(body["preview_mtime"], (int, float))
    assert body["preview_mtime"] > 0


def test_chat_sse_error_event_on_failure(client: TestClient, tmp_path: Path, monkeypatch):
    (tmp_path / "take.mp4").write_bytes(b"x")
    (tmp_path / "edit").mkdir(exist_ok=True)
    (tmp_path / "edit" / "takes_packed.md").write_text("x", encoding="utf-8")
    client.post("/api/folder", json={"path": str(tmp_path)})
    import app.server.main as main_mod

    def boom(*_a, **_k):
        raise RuntimeError("claude failed")
        yield  # pragma: no cover

    monkeypatch.setattr(main_mod, "stream_claude", boom)
    monkeypatch.setattr(main_mod, "_chat_enabled", lambda _folder: True)
    r = client.post("/api/chat", json={"message": "hi"})
    assert r.status_code == 200
    assert '"error": "claude failed"' in r.text
    assert '"done": true' in r.text
