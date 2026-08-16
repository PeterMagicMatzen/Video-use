"""Backend regression for reel-editor features: cloudinary status, project library,
thumbnail, /reel settings, export (9:16 karaoke + original + range/download), invalid
aspect, non-ready export, deletion."""
import os
import time
import requests
import pytest

def _read_frontend_env():
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip()
    except FileNotFoundError:
        pass
    return ""

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _read_frontend_env()).rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL missing"
API = f"{BASE_URL}/api"
VIDEO = "/app/memory/testvid.mp4"


def _upload_project():
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
    assert r.status_code == 200
    deadline = time.time() + 90
    while time.time() < deadline:
        r = requests.get(f"{API}/projects/{pid}", timeout=15)
        assert r.status_code == 200
        st = r.json().get("status")
        if st == "ready":
            return pid
        if st == "error":
            pytest.fail(f"transcription error: {r.json().get('error')}")
        time.sleep(2)
    pytest.fail("project did not become ready")


@pytest.fixture(scope="module")
def pid():
    p = _upload_project()
    yield p
    # cleanup
    try:
        requests.delete(f"{API}/projects/{p}", timeout=15)
    except Exception:
        pass


# ---------- basic ----------

def test_cloudinary_status():
    r = requests.get(f"{API}/cloudinary/status", timeout=15)
    assert r.status_code == 200
    j = r.json()
    assert j["enabled"] is False
    assert j["cloud_name"] in (None, "")


def test_list_projects_shape():
    r = requests.get(f"{API}/projects", timeout=15)
    assert r.status_code == 200
    j = r.json()
    assert isinstance(j.get("projects"), list)
    if j["projects"]:
        item = j["projects"][0]
        for k in ("id", "filename", "status", "export_status", "has_thumb"):
            assert k in item, f"missing key {k} in {item}"


def test_thumbnail_returns_jpeg(pid):
    r = requests.get(f"{API}/projects/{pid}/thumbnail", timeout=30)
    assert r.status_code == 200
    assert r.headers.get("Content-Type", "").startswith("image/jpeg")
    assert len(r.content) > 500


# ---------- reel settings ----------

def test_set_reel_valid(pid):
    r = requests.post(f"{API}/projects/{pid}/reel", json={
        "aspect": "9:16", "cinematic": True, "karaoke": True,
        "zoom_intensity": 1.2, "burn_captions": True,
    }, timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["reel_settings"]["aspect"] == "9:16"
    assert j["reel_settings"]["cinematic"] is True
    assert j["reel_settings"]["karaoke"] is True
    assert abs(j["reel_settings"]["zoom_intensity"] - 1.2) < 1e-6
    cuts = j.get("cuts")
    assert cuts is not None
    assert isinstance(cuts.get("moves"), list) and len(cuts["moves"]) > 0
    # verify persistence
    r2 = requests.get(f"{API}/projects/{pid}", timeout=15)
    assert r2.json()["reel_settings"]["aspect"] == "9:16"


def test_set_reel_invalid_aspect(pid):
    r = requests.post(f"{API}/projects/{pid}/reel", json={
        "aspect": "4:5", "cinematic": True, "karaoke": True,
        "zoom_intensity": 1.0, "burn_captions": True,
    }, timeout=15)
    assert r.status_code == 400


# ---------- export flows ----------

def _wait_export(pid: str, timeout: int = 240):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        r = requests.get(f"{API}/projects/{pid}", timeout=15)
        assert r.status_code == 200
        exp = r.json().get("export") or {}
        last = exp
        if exp.get("status") == "done":
            return exp
        if exp.get("status") == "error":
            pytest.fail(f"export error: {exp.get('error')}")
        time.sleep(3)
    pytest.fail(f"export not done in time, last={last}")


def test_export_vertical_karaoke(pid):
    r = requests.post(f"{API}/projects/{pid}/export", json={
        "caption_style": "bold", "burn_captions": True,
        "aspect": "9:16", "cinematic": True, "karaoke": True, "zoom_intensity": 1.0,
    }, timeout=30)
    assert r.status_code == 200, r.text

    # second export while processing => 400
    r2 = requests.post(f"{API}/projects/{pid}/export", json={
        "caption_style": "bold", "aspect": "9:16",
    }, timeout=15)
    assert r2.status_code == 400

    exp = _wait_export(pid)
    meta = exp.get("meta") or {}
    assert meta.get("width") == 1080
    assert meta.get("height") == 1920
    assert meta.get("karaoke") is True
    assert isinstance(meta.get("moves"), list)
    # moves length equals kept ranges (as documented)
    st = requests.get(f"{API}/projects/{pid}", timeout=15).json()
    kept = (st.get("cuts") or {}).get("keep_ranges") or []
    assert len(meta["moves"]) == len(kept)
    assert (meta.get("caption_events") or 0) > 0


def test_export_video_range_and_download(pid):
    r = requests.get(f"{API}/projects/{pid}/export/video",
                     headers={"Range": "bytes=0-1023"}, timeout=15)
    assert r.status_code == 206
    assert r.headers.get("Content-Type", "").startswith("video/")

    d = requests.get(f"{API}/projects/{pid}/export/download", timeout=30)
    assert d.status_code == 200
    assert d.headers.get("Content-Type", "").startswith("video/mp4")
    assert "attachment" in (d.headers.get("Content-Disposition") or "").lower()


def test_export_original_no_karaoke(pid):
    r = requests.post(f"{API}/projects/{pid}/export", json={
        "caption_style": "minimal", "burn_captions": True,
        "aspect": "original", "cinematic": True, "karaoke": False, "zoom_intensity": 1.0,
    }, timeout=30)
    assert r.status_code == 200, r.text
    exp = _wait_export(pid)
    meta = exp.get("meta") or {}
    assert meta.get("karaoke") is False


# ---------- error cases ----------

def test_export_when_not_ready():
    # Create fresh project but do NOT complete transcription first — attempt export before ready
    size = os.path.getsize(VIDEO)
    r = requests.post(f"{API}/projects/upload/init",
                      json={"filename": "testvid.mp4", "size": size}, timeout=30)
    pid_new = r.json()["project_id"]
    # try to export immediately — status will be 'uploading' or 'transcribing', not 'ready'
    r = requests.post(f"{API}/projects/{pid_new}/export", json={"caption_style": "bold"}, timeout=15)
    assert r.status_code == 400
    requests.delete(f"{API}/projects/{pid_new}", timeout=15)


def test_delete_project():
    p = _upload_project()
    r = requests.delete(f"{API}/projects/{p}", timeout=15)
    assert r.status_code == 200
    r2 = requests.get(f"{API}/projects/{p}", timeout=15)
    assert r2.status_code == 404
