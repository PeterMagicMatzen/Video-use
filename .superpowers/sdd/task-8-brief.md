### Task 8: transcribe + pack job

**Files:**
- Create: `app/server/jobs.py`
- Modify: `app/server/main.py`
- Modify: `tests/test_api.py`

**Interfaces:**
- Consumes: `run_helper`, session, `CURRENT_FOLDER`
- Produces:

```python
def start_transcribe(folder: Path) -> dict
# raises RuntimeError if job.kind != idle
# runs in a thread:
#   python helpers/transcribe_batch.py <folder>
#   python helpers/pack_transcripts.py --edit-dir <folder>/edit
# on Scribe 401/quota: last_error = "ElevenLabs rejected the key. Check Developer/video-use/.env"
# never include response body that might contain the key
```

Routes:

- `POST /api/transcribe` → 409 if no folder or job busy; 400 if doctor elevenlabs/ffmpeg not ok; else 202 `{ "accepted": true }`
- Poll via existing `GET /api/state`

Do not start transcribe from `POST /api/folder`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_api.py`:

```python
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
```

Add `tests/test_jobs.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_api.py tests/test_jobs.py -v`

Expected: FAIL — `start_transcribe` missing and/or `/api/transcribe` 404

- [ ] **Step 3: Implement job runner and route**

`app/server/jobs.py`:

```python
from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path

from app.server.proc import run_helper
from app.server.session import load_session, save_session


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def start_transcribe(folder: Path) -> dict:
    session = load_session(folder)
    if (session.get("job") or {}).get("kind") not in (None, "idle"):
        raise RuntimeError("busy")
    log = folder / "edit" / "transcribe.log"
    session["last_error"] = None
    session["job"] = {"kind": "transcribe", "pid": None, "started_at": _now(), "output": None, "log": str(log)}
    save_session(folder, session)

    def work():
        s = load_session(folder)
        try:
            batch = run_helper("transcribe_batch.py", [str(folder)])
            log.write_text((batch.stdout or "") + (batch.stderr or ""), encoding="utf-8")
            if batch.returncode != 0:
                text = (batch.stderr or batch.stdout or "")
                if "401" in text or "quota" in text.lower() or "returned 401" in text:
                    raise RuntimeError("ElevenLabs rejected the key. Check Developer/video-use/.env")
                raise RuntimeError(text[-400:] or "transcribe failed")
            packed = run_helper("pack_transcripts.py", ["--edit-dir", str(folder / "edit")])
            log.write_text(log.read_text(encoding="utf-8") + (packed.stdout or "") + (packed.stderr or ""), encoding="utf-8")
            if packed.returncode != 0:
                raise RuntimeError((packed.stderr or packed.stdout or "pack failed")[-400:])
            s = load_session(folder)
            s["last_error"] = None
        except Exception as exc:
            s = load_session(folder)
            s["last_error"] = str(exc)
        finally:
            s["job"] = {"kind": "idle", "pid": None, "started_at": None, "output": None, "log": str(log)}
            save_session(folder, s)

    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    # store a sentinel pid so reclaim does not immediately clear; use current pid
    import os
    session = load_session(folder)
    session["job"]["pid"] = os.getpid()
    save_session(folder, session)
    return {"accepted": True}
```

Using the API process pid is intentional: the job lives in a thread of this process. Reclaim on reboot sees this pid dead and marks failed.

Wire `POST /api/transcribe` in `main.py`. Import `start_transcribe` from `app.server.jobs`.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_api.py tests/test_jobs.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/server/jobs.py app/server/main.py tests/test_api.py tests/test_jobs.py
git commit -m "feat: explicit transcribe and pack job"
```

---

