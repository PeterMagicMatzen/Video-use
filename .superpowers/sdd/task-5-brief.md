### Task 5: inventory + recents + helper subprocess env

**Files:**
- Create: `app/server/proc.py`
- Create: `app/server/recents.py`
- Create: `app/server/inventory.py`
- Create: `tests/test_inventory.py`

**Interfaces:**
- Consumes: `HELPERS`, `APP_HOME` from Task 4
- Produces:

```python
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".m4v", ".webm", ".avi"}

def helper_env() -> dict   # os.environ + PYTHONIOENCODING=utf-8 + PYTHONUTF8=1
def find_videos(folder: Path) -> list[Path]
def probe_source(path: Path, *, run=subprocess.run) -> dict
# {name, path, duration_s, width, height, fps, error}
def inventory(folder: Path, *, run=subprocess.run) -> list[dict]
def add_recent(folder: Path) -> list[str]
def load_recents() -> list[str]
```

`probe_source` runs:

`ffprobe -v error -show_entries format=duration -show_entries stream=width,height,avg_frame_rate,codec_type -of json <path>`

Parse the first video stream. On failure set `error` to stderr snippet, numeric fields to `None`.

Recents file: `APP_HOME / "recents.json"` — JSON array of absolute paths, most recent first, max 10, de-duplicated.

- [ ] **Step 1: Write the failing tests**

`tests/test_inventory.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from app.server.inventory import VIDEO_EXTS, find_videos, probe_source
from app.server.proc import helper_env
from app.server.recents import add_recent, load_recents


def test_find_videos_filters(tmp_path: Path):
    (tmp_path / "a.MP4").write_bytes(b"x")
    (tmp_path / "b.webm").write_bytes(b"x")
    (tmp_path / "note.txt").write_bytes(b"x")
    (tmp_path / "edit").mkdir()
    names = {p.name for p in find_videos(tmp_path)}
    assert names == {"a.MP4", "b.webm"}
    assert ".webm" in VIDEO_EXTS


def test_helper_env_forces_utf8(monkeypatch):
    monkeypatch.setenv("FOO", "1")
    env = helper_env()
    assert env["PYTHONIOENCODING"] == "utf-8"
    assert env["PYTHONUTF8"] == "1"
    assert env["FOO"] == "1"


def test_probe_parses_ffprobe():
    payload = {
        "format": {"duration": "12.5"},
        "streams": [
            {"codec_type": "audio"},
            {"codec_type": "video", "width": 1920, "height": 1080, "avg_frame_rate": "30000/1001"},
        ],
    }
    def run(cmd, **kwargs):
        class R:
            returncode = 0
            stdout = json.dumps(payload)
            stderr = ""
        return R()
    info = probe_source(Path("C:/a.mp4"), run=run)
    assert info["duration_s"] == 12.5
    assert info["width"] == 1920
    assert info["height"] == 1080
    assert info["error"] is None


def test_recents_cap_and_dedupe(tmp_path, monkeypatch):
    from app.server import recents as recents_mod
    monkeypatch.setattr(recents_mod, "RECENTS_PATH", tmp_path / "recents.json")
    for i in range(12):
        add_recent(Path(f"C:/f/{i}"))
    add_recent(Path("C:/f/11"))
    items = load_recents()
    assert items[0].endswith("11")
    assert len(items) == 10
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_inventory.py -v`

Expected: FAIL with import error

- [ ] **Step 3: Implement proc, recents, inventory**

`app/server/proc.py`:

```python
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from app.server.paths import HELPERS


def helper_env() -> dict:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def run_helper(script: str, args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess:
    cmd = ["python", str(HELPERS / script), *args]
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=helper_env(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
```

`app/server/recents.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from app.server.paths import APP_HOME

RECENTS_PATH = APP_HOME / "recents.json"
MAX_RECENTS = 10


def load_recents() -> list[str]:
    if not RECENTS_PATH.exists():
        return []
    data = json.loads(RECENTS_PATH.read_text(encoding="utf-8"))
    return [str(p) for p in data] if isinstance(data, list) else []


def add_recent(folder: Path) -> list[str]:
    resolved = str(folder.resolve())
    items = [resolved, *[p for p in load_recents() if p != resolved]]
    items = items[:MAX_RECENTS]
    RECENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RECENTS_PATH.write_text(json.dumps(items, indent=2), encoding="utf-8")
    return items
```

`app/server/inventory.py`:

```python
from __future__ import annotations

import json
import subprocess
from pathlib import Path

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".m4v", ".webm", ".avi"}


def find_videos(folder: Path) -> list[Path]:
    return sorted(
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in VIDEO_EXTS
    )


def _fps(rate: str | None) -> float | None:
    if not rate or rate in ("0/0", "N/A"):
        return None
    if "/" in rate:
        a, b = rate.split("/", 1)
        try:
            return float(a) / float(b)
        except (TypeError, ValueError, ZeroDivisionError):
            return None
    try:
        return float(rate)
    except (TypeError, ValueError):
        return None


def probe_source(path: Path, *, run=subprocess.run) -> dict:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-show_entries", "stream=width,height,avg_frame_rate,codec_type",
        "-of", "json",
        str(path),
    ]
    proc = run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    info = {
        "name": path.name,
        "path": str(path.resolve()),
        "duration_s": None,
        "width": None,
        "height": None,
        "fps": None,
        "error": None,
    }
    if proc.returncode != 0:
        info["error"] = (proc.stderr or "ffprobe failed")[:400]
        return info
    try:
        payload = json.loads(proc.stdout or "{}")
        dur = (payload.get("format") or {}).get("duration")
        info["duration_s"] = float(dur) if dur is not None else None
        for stream in payload.get("streams") or []:
            if stream.get("codec_type") == "video":
                info["width"] = stream.get("width")
                info["height"] = stream.get("height")
                info["fps"] = _fps(stream.get("avg_frame_rate"))
                break
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        info["error"] = str(exc)
    return info


def inventory(folder: Path, *, run=subprocess.run) -> list[dict]:
    return [probe_source(p, run=run) for p in find_videos(folder)]
```

Also add `.webm` / `.WEBM` to `VIDEO_EXTS` in `helpers/transcribe_batch.py` so batch transcribe sees the same files as inventory.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_inventory.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/server/proc.py app/server/recents.py app/server/inventory.py helpers/transcribe_batch.py tests/test_inventory.py
git commit -m "feat: inventory sources and remember recent folders"
```

---

