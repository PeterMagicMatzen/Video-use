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
