### Task 6: center-state derivation

**Files:**
- Create: `app/server/state.py`
- Create: `tests/test_state.py`

**Interfaces:**
- Consumes: session dict from Task 4; files on disk under `folder/edit/`
- Produces: `CenterState` literal and `derive_center_state(folder: Path, session: dict) -> str`

States, first match wins:

| Condition | State |
|---|---|
| `session["job"]["kind"] == "transcribe"` | `transcribing` |
| `session["job"]["kind"] == "render"` | `rendering` |
| `session["job"]["kind"] == "claude"` | keep evaluating files; do not override to a dedicated state |
| no folder / folder missing / no videos | `empty` |
| videos exist, no `edit/takes_packed.md` | `inventory` |
| `session["last_error"]` set | `error` |
| packed exists, no `edit/edl.json` | `packed` |
| `edl.json` exists and (`edl_mtime > edl_mtime_at_approve` or chat completed after approve with no new approve) — implement chat-stale as `session.get("chat_after_approve") is True` | `stale` |
| `edl.json` exists, not stale, no `preview.mp4` | `strategy-ready` |
| `preview.mp4` exists and not stale | `preview-ready` |

`chat_after_approve` is a boolean the Claude adapter sets to `True` after a non-approve chat turn, and `False` on successful approve.

- [ ] **Step 1: Write the failing tests**

`tests/test_state.py`:

```python
from __future__ import annotations

from pathlib import Path

from app.server.session import default_session
from app.server.state import derive_center_state


def _folder(tmp: Path, videos=True, packed=False, edl=False, preview=False) -> Path:
    if videos:
        (tmp / "a.mp4").write_bytes(b"x")
    edit = tmp / "edit"
    edit.mkdir(exist_ok=True)
    if packed:
        (edit / "takes_packed.md").write_text("x", encoding="utf-8")
    if edl:
        (edit / "edl.json").write_text("{}", encoding="utf-8")
    if preview:
        (edit / "preview.mp4").write_bytes(b"x")
    return tmp


def test_empty(tmp_path: Path):
    assert derive_center_state(tmp_path, default_session(tmp_path)) == "empty"


def test_inventory(tmp_path: Path):
    _folder(tmp_path)
    assert derive_center_state(tmp_path, default_session(tmp_path)) == "inventory"


def test_transcribing(tmp_path: Path):
    _folder(tmp_path)
    s = default_session(tmp_path)
    s["job"]["kind"] = "transcribe"
    s["job"]["pid"] = 1
    assert derive_center_state(tmp_path, s) == "transcribing"


def test_packed(tmp_path: Path):
    _folder(tmp_path, packed=True)
    assert derive_center_state(tmp_path, default_session(tmp_path)) == "packed"


def test_error_after_pack(tmp_path: Path):
    _folder(tmp_path, packed=True)
    s = default_session(tmp_path)
    s["last_error"] = "Scribe returned 401"
    assert derive_center_state(tmp_path, s) == "error"


def test_strategy_ready(tmp_path: Path):
    _folder(tmp_path, packed=True, edl=True)
    s = default_session(tmp_path)
    s["edl_mtime_at_approve"] = (tmp_path / "edit" / "edl.json").stat().st_mtime
    s["chat_after_approve"] = False
    assert derive_center_state(tmp_path, s) == "strategy-ready"


def test_stale_after_chat(tmp_path: Path):
    _folder(tmp_path, packed=True, edl=True, preview=True)
    s = default_session(tmp_path)
    s["edl_mtime_at_approve"] = (tmp_path / "edit" / "edl.json").stat().st_mtime
    s["chat_after_approve"] = True
    assert derive_center_state(tmp_path, s) == "stale"


def test_preview_ready(tmp_path: Path):
    _folder(tmp_path, packed=True, edl=True, preview=True)
    s = default_session(tmp_path)
    s["edl_mtime_at_approve"] = (tmp_path / "edit" / "edl.json").stat().st_mtime
    s["chat_after_approve"] = False
    assert derive_center_state(tmp_path, s) == "preview-ready"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_state.py -v`

Expected: FAIL with import error for `app.server.state`

- [ ] **Step 3: Implement `app/server/state.py`**

```python
from __future__ import annotations

from pathlib import Path

from app.server.inventory import find_videos

CENTER_STATES = (
    "empty", "inventory", "transcribing", "packed",
    "strategy-ready", "rendering", "preview-ready", "stale", "error",
)


def derive_center_state(folder: Path, session: dict) -> str:
    job_kind = (session.get("job") or {}).get("kind")
    if job_kind == "transcribe":
        return "transcribing"
    if job_kind == "render":
        return "rendering"
    if not folder.exists() or not find_videos(folder):
        return "empty"
    edit = folder / "edit"
    packed = edit / "takes_packed.md"
    edl = edit / "edl.json"
    preview = edit / "preview.mp4"
    if not packed.exists():
        return "inventory"
    if session.get("last_error"):
        return "error"
    if not edl.exists():
        return "packed"
    approved_mtime = float(session.get("edl_mtime_at_approve") or 0)
    stale = bool(session.get("chat_after_approve")) or edl.stat().st_mtime > approved_mtime + 0.001
    if stale:
        return "stale"
    if not preview.exists():
        return "strategy-ready"
    return "preview-ready"
```

Note: `strategy-ready` is used when an EDL exists and is not stale but preview is missing. A freshly written unapproved EDL should be stale if `edl_mtime_at_approve` is 0 (default). That means Claude writing an EDL *before* approve would show `stale` — which is correct because the user must Approve. After approve, `edl_mtime_at_approve` is set to the file mtime, `chat_after_approve=False`, preview missing → `strategy-ready` only if we set mtime *before* render. Approve flow in Task 8/9 must:

1. Claude writes EDL
2. validate
3. set `edl_mtime_at_approve` to current mtime, `chat_after_approve=False`
4. start render (`rendering`)
5. on success, preview exists → `preview-ready`

Until step 3, if Claude wrote early, state is `stale`. Tests above set mtime equal so they hit `strategy-ready`.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_state.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/server/state.py tests/test_state.py
git commit -m "feat: derive review-panel center state"
```

---

