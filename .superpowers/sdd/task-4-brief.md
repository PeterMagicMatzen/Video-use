### Task 4: session file + dead-pid reclaim

**Files:**
- Create: `app/__init__.py` (empty)
- Create: `app/server/__init__.py` (empty)
- Create: `app/server/paths.py`
- Create: `app/server/session.py`
- Create: `tests/test_session.py`

**Interfaces:**
- Consumes: nothing
- Produces:

```python
# app/server/paths.py
REPO_ROOT: Path   # parents[2] from this file
HELPERS: Path     # REPO_ROOT / "helpers"
APP_HOME: Path    # Path.home() / ".video-use"

# app/server/session.py
JOB_KINDS = ("idle", "transcribe", "claude", "render")

def default_session(folder: Path) -> dict
def session_path(folder: Path) -> Path   # folder / "edit" / "app_session.json"
def load_session(folder: Path) -> dict
def save_session(folder: Path, data: dict) -> None
def pid_alive(pid: int | None) -> bool
def reclaim_job(data: dict) -> dict
# reclaim: if job.kind != idle and job.pid set and not pid_alive, set
#   data["job"] = {kind: "idle", pid: None, started_at: None, output: None, log: None}
#   data["last_error"] = "previous {old_kind} job died (pid {pid})"
```

`default_session` shape:

```python
{
  "claude_session_id": None,
  "folder": str(folder.resolve()),
  "edl_approved_at": None,
  "edl_mtime_at_approve": 0,
  "last_error": None,
  "job": {"kind": "idle", "pid": None, "started_at": None, "output": None, "log": None},
}
```

- [ ] **Step 1: Write the failing tests**

`tests/test_session.py`:

```python
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
    assert "render" in (out.get("last_error") or "")


def test_reclaim_keeps_live_pid():
    import os
    data = default_session(Path("C:/footage"))
    data["job"] = {"kind": "transcribe", "pid": os.getpid(), "started_at": "t", "output": None, "log": None}
    out = reclaim_job(data)
    assert out["job"]["kind"] == "transcribe"
    assert out["job"]["pid"] == os.getpid()


def test_pid_alive_false_for_none():
    assert pid_alive(None) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_session.py -v`

Expected: FAIL with import error for `app.server.session`

- [ ] **Step 3: Implement paths + session**

`app/__init__.py` and `app/server/__init__.py`: empty files.

`app/server/paths.py`:

```python
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HELPERS = REPO_ROOT / "helpers"
APP_HOME = Path.home() / ".video-use"
```

`app/server/session.py`:

```python
from __future__ import annotations

import json
import os
from pathlib import Path

JOB_KINDS = ("idle", "transcribe", "claude", "render")


def default_session(folder: Path) -> dict:
    return {
        "claude_session_id": None,
        "folder": str(folder.resolve()),
        "edl_approved_at": None,
        "edl_mtime_at_approve": 0,
        "last_error": None,
        "job": {"kind": "idle", "pid": None, "started_at": None, "output": None, "log": None},
    }


def session_path(folder: Path) -> Path:
    return folder / "edit" / "app_session.json"


def load_session(folder: Path) -> dict:
    path = session_path(folder)
    if not path.exists():
        return default_session(folder)
    data = json.loads(path.read_text(encoding="utf-8"))
    base = default_session(folder)
    base.update(data)
    if not isinstance(base.get("job"), dict):
        base["job"] = default_session(folder)["job"]
    return reclaim_job(base)


def save_session(folder: Path, data: dict) -> None:
    path = session_path(folder)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def reclaim_job(data: dict) -> dict:
    job = data.get("job") or {}
    kind = job.get("kind") or "idle"
    pid = job.get("pid")
    if kind != "idle" and pid and not pid_alive(int(pid)):
        data["last_error"] = f"previous {kind} job died (pid {pid})"
        data["job"] = {"kind": "idle", "pid": None, "started_at": None, "output": None, "log": None}
    return data
```

On Windows `os.kill(pid, 0)` works for a same-user process check. `PermissionError` means the pid exists; `OSError` / `ProcessLookupError` means it does not.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_session.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/__init__.py app/server/__init__.py app/server/paths.py app/server/session.py tests/test_session.py
git commit -m "feat: persist edit/app_session.json and reclaim dead jobs"
```

---

