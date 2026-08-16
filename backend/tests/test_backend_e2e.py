"""Backend regression: upload -> transcribe -> ready -> cuts -> style -> export -> download."""
import os
import time
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or \
           "https://da04ce3d-af98-47de-8041-35ba8b318b03.preview.emergentagent.com"
API = f"{BASE_URL}/api"
VIDEO = "/app/memory/testvid.mp4"


@pytest.fixture(scope="module")
def project_id():
    size = os.path.getsize(VIDEO)
    r = requests.post(f"{API}/projects/upload/init",
                      json={"filename": "testvid.mp4", "size": size}, timeout=30)
    assert r.status_code == 200, r.text
    pid = r.json()["project_id"]
    with open(VIDEO, "rb") as f:
        data = f.read()
    files = {"chunk": ("chunk", data, "application/octet-stream")}
    r = requests.post(f"{API}/projects/{pid}/upload/chunk",
                      data={"index": 0}, files=files, timeout=60)
    assert r.status_code == 200, r.text
    r = requests.post(f"{API}/projects/{pid}/upload/complete", timeout=60)
    assert r.status_code == 200, r.text
    # Poll ready
    deadline = time.time() + 60
    status = None
    while time.time() < deadline:
        r = requests.get(f"{API}/projects/{pid}", timeout=15)
        assert r.status_code == 200
        status = r.json().get("status")
        if status == "ready":
            return pid
        if status == "error":
            pytest.fail(f"Transcription error: {r.json().get('error')}")
        time.sleep(2)
    pytest.fail(f"Project not ready in time, last status={status}")


def test_project_ready_has_words(project_id):
    r = requests.get(f"{API}/projects/{project_id}", timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ready"
    assert isinstance(data.get("words"), list) and len(data["words"]) > 0
    assert data.get("cuts") is not None


def test_cuts_update(project_id):
    r = requests.post(f"{API}/projects/{project_id}/cuts",
                      json={"pause_threshold": 0.8, "remove_fillers": True, "disabled": []},
                      timeout=15)
    assert r.status_code == 200, r.text
    cuts = r.json()
    assert "spans" in cuts and "kept_duration" in cuts and "removed_duration" in cuts


def test_style_update(project_id):
    r = requests.post(f"{API}/projects/{project_id}/style",
                      json={"caption_style": "neon"}, timeout=15)
    assert r.status_code == 200


def test_video_streaming(project_id):
    r = requests.get(f"{API}/projects/{project_id}/video",
                     headers={"Range": "bytes=0-1023"}, timeout=15)
    assert r.status_code in (200, 206)
    assert r.headers.get("Content-Type", "").startswith("video/")
