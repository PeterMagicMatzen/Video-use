### Task 10: approve + preview + final render

**Files:**
- Modify: `app/server/jobs.py`
- Modify: `app/server/main.py`
- Modify: `tests/test_jobs.py`
- Modify: `tests/test_api.py`

**Interfaces:**
- Consumes: `stream_claude`, `validate_edl`, `run_helper("render.py", ...)`
- Produces:

```python
def start_approve_and_preview(folder: Path) -> dict
# 1) stream_claude(APPROVE_PROMPT)
# 2) load edit/edl.json; validate_edl; if not ok: last_error = join(errors); return
# 3) set edl_mtime_at_approve, chat_after_approve=False, edl_approved_at=now
# 4) start_render(folder, preview=True)

def start_render(folder: Path, *, preview: bool) -> dict
# 409/RuntimeError if busy
# validate EDL first; never call ffmpeg on invalid
# preview: helpers/render.py edit/edl.json -o edit/preview.mp4 --preview
#          plus --build-subtitles if edl has subtitles and (master.srt missing or older than edl)
# final:   helpers/render.py edit/edl.json -o edit/final.mp4  (same subtitle rule)
# on CalledProcessError: last_error = last 40 lines of stderr; leave preview.mp4 in place
```

Routes:

- `POST /api/approve` → 202
- `POST /api/render-final` → 202
- `GET /api/media/preview` → FileResponse `edit/preview.mp4` or 404
- `GET /api/media/source/{name}` → FileResponse of that source or 404
- `GET /api/media/final` → FileResponse `edit/final.mp4` or 404

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_jobs.py`:

```python
from app.server.jobs import start_render
from app.server.session import default_session, save_session


def test_start_render_rejects_invalid_edl(tmp_path: Path, monkeypatch):
    (tmp_path / "a.mp4").write_bytes(b"x")
    edit = tmp_path / "edit"
    edit.mkdir()
    (edit / "edl.json").write_text('{"sources":{},"ranges":[]}', encoding="utf-8")
    save_session(tmp_path, default_session(tmp_path))
    called = {"n": 0}
    from app.server import proc as proc_mod
    monkeypatch.setattr(proc_mod, "run_helper", lambda *a, **k: called.__setitem__("n", called["n"] + 1))
    with pytest.raises(RuntimeError, match="invalid"):
        start_render(tmp_path, preview=True)
    assert called["n"] == 0
```

Add to `tests/test_api.py`:

```python
def test_approve_route_exists(client: TestClient, tmp_path: Path, monkeypatch):
    (tmp_path / "take.mp4").write_bytes(b"x")
    (tmp_path / "edit").mkdir()
    (tmp_path / "edit" / "takes_packed.md").write_text("x", encoding="utf-8")
    client.post("/api/folder", json={"path": str(tmp_path)})
    import app.server.main as main_mod
    monkeypatch.setattr(main_mod, "start_approve_and_preview", lambda folder: {"accepted": True})
    r = client.post("/api/approve")
    assert r.status_code == 202
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_jobs.py tests/test_api.py -v`

Expected: FAIL — `start_render` / `/api/approve` missing

- [ ] **Step 3: Implement approve + render**

In `start_render`, after a successful preview, do not clear `preview.mp4` on a later failure. Write ffmpeg stderr to `edit/render.log`.

Subtitle flag:

```python
def should_build_subtitles(edl: dict, edit_dir: Path) -> bool:
    if not edl.get("subtitles"):
        return False
    srt = edit_dir / "master.srt"
    edl_path = edit_dir / "edl.json"
    if not srt.exists():
        return True
    return srt.stat().st_mtime < edl_path.stat().st_mtime
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_jobs.py tests/test_api.py tests/test_edl.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/server/jobs.py app/server/main.py tests/test_jobs.py tests/test_api.py
git commit -m "feat: approve writes EDL then API renders preview"
```

---

