### Task 7: FastAPI skeleton — doctor, folder, browse, state

**Files:**
- Create: `app/server/main.py`
- Create: `app/__main__.py`
- Create: `tests/test_api.py`
- Modify: `helpers/transcribe_batch.py` already done for webm

**Interfaces:**
- Consumes: doctor, inventory, recents, session, state
- Produces: FastAPI app `app` in `app/server/main.py`

In-memory (process-global) `CURRENT_FOLDER: Path | None`.

Routes:

- `GET /api/doctor` → `run_doctor().to_dict()`
- `GET /api/recents` → `{ "recents": load_recents() }`
- `POST /api/folder` body `{ "path": "C:\\..." }` → open folder, mkdir `edit/`, `add_recent`, `load_session`, return `project_payload()`
- `POST /api/folder/browse` → tkinter `askdirectory`, then same as folder if not cancelled `{ "cancelled": true }`
- `GET /api/state` → `project_payload()` or 404 if no folder
- `POST /api/open-edit` → `os.startfile(str(folder / "edit"))` on win32

`project_payload()`:

```python
{
  "folder": str,
  "doctor": run_doctor().to_dict(),
  "sources": inventory(folder),
  "recents": load_recents(),
  "center_state": derive_center_state(folder, session),
  "error": session.get("last_error"),
  "packed_markdown": text or null,
  "edl": object or null,
  "has_preview": bool,
  "has_final": bool,
  "chat_enabled": packed exists and doctor.ok,
  "job": session["job"],
  "stale": center_state == "stale",
}
```

CORS allow `http://localhost:5173`.

Do **not** add a transcribe route in this task.

- [ ] **Step 1: Write the failing tests**

`tests/test_api.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pip install -e ".[app,dev]"` then `pytest tests/test_api.py -v`

Expected: FAIL with import error for `app.server.main`

- [ ] **Step 3: Implement `app/server/main.py` and `app/__main__.py`**

`app/__main__.py`:

```python
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.server.main:app", host="127.0.0.1", port=8787, reload=True)
```

`app/server/main.py` — implement the routes listed in Interfaces. Include:

```python
from fastapi.middleware.cors import CORSMiddleware

CURRENT_FOLDER: Path | None = None

def reset_current_folder() -> None:
    global CURRENT_FOLDER
    CURRENT_FOLDER = None
```

Browse dialog:

```python
def pick_folder_dialog() -> str | None:
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.wm_attributes("-topmost", 1)
    chosen = filedialog.askdirectory()
    root.destroy()
    return chosen or None
```

`POST /api/folder/browse` is hard to unit test (GUI). Do not test the dialog in pytest; test only `/api/folder`.

For `GET /api/state` 404: `{"detail": "no folder open"}`.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_api.py tests/test_state.py tests/test_session.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/server/main.py app/__main__.py tests/test_api.py
git commit -m "feat: FastAPI doctor and folder endpoints"
```

---

