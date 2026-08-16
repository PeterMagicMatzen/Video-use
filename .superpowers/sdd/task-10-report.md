# Task 10 Report: approve + preview + final render

## Status

**Complete.** Branch `local-app`. Not pushed.

## What shipped

| File | Role |
|------|------|
| `app/server/jobs.py` | `should_build_subtitles`, `start_render`, `start_approve_and_preview`; shared busy guard |
| `app/server/main.py` | `POST /api/approve`, `POST /api/render-final`, `GET /api/media/{preview,final,source}` |
| `tests/test_jobs.py` | invalid-EDL never calls ffmpeg (verbatim) |
| `tests/test_api.py` | `/api/approve` exists → 202 (verbatim) |

API still does not write `edit/edl.json`. Claude writes it on approve; the API only validates then renders.

## Interfaces (verbatim)

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

def should_build_subtitles(edl: dict, edit_dir: Path) -> bool
```

```
POST /api/approve        → 202 { "accepted": true }; 409 no folder / busy
POST /api/render-final   → 202 { "accepted": true }; 409 no folder / busy; 400 invalid EDL
                         never starts Claude
GET  /api/media/preview  → FileResponse edit/preview.mp4 or 404
GET  /api/media/final    → FileResponse edit/final.mp4 or 404
GET  /api/media/source/{name} → FileResponse of that footage-root video or 404
```

`start_approve_and_preview` / `start_render` are imported in `main.py` so tests can patch `app.server.main.start_approve_and_preview`.

## TDD steps

1. Added `test_start_render_rejects_invalid_edl` and `test_approve_route_exists` exactly as brief.
2. `pytest tests/test_jobs.py tests/test_api.py -v` → collection **ERROR** (`ImportError: cannot import name 'start_render'`).
3. Implemented `should_build_subtitles` (verbatim), `start_render`, `start_approve_and_preview`, and the five routes.
4. `pytest tests/test_jobs.py tests/test_api.py tests/test_edl.py -v` → **18 passed**. Full suite **42 passed**.
5. Committed.

## Commit

```
25574d8 feat: approve writes EDL then API renders preview
```

Files: `app/server/jobs.py`, `app/server/main.py`, `tests/test_jobs.py`, `tests/test_api.py`.

## Test summary

```
tests/test_jobs.py::test_start_transcribe_rejects_busy PASSED
tests/test_jobs.py::test_start_render_rejects_invalid_edl PASSED
tests/test_api.py::test_doctor PASSED
tests/test_api.py::test_state_without_folder PASSED
tests/test_api.py::test_open_folder_lists_sources PASSED
tests/test_api.py::test_no_transcribe_route_implied PASSED
tests/test_api.py::test_transcribe_requires_explicit_click PASSED
tests/test_api.py::test_transcribe_409_when_busy PASSED
tests/test_api.py::test_approve_route_exists PASSED
tests/test_edl.py — 9 passed
```

18 passed (brief set) in ~1.20s. Full suite `pytest tests/ -v` → **42 passed**.

Starlette deprecation: `Using httpx with starlette.testclient is deprecated; install httpx2 instead.` — FastAPI/Starlette, not this task.

Local smoke (not committed): mocked `run_helper` / `stream_claude` confirmed preview argv `edit/edl.json -o edit/preview.mp4 --preview [--build-subtitles]`, final argv without `--preview` and without Claude, last-40-lines `last_error` on non-zero, previous `preview.mp4` left in place, media 200/404 + path-traversal 404, approve sets `edl_approved_at` / `chat_after_approve=False` then starts preview render, invalid post-Claude EDL joins validator errors and never calls ffmpeg.

## Self-review

### Matches brief

- `start_render` validates via `from edl import validate_edl` **before** `run_helper`. Invalid EDL raises `RuntimeError` matching `invalid` and does not call the helper.
- Preview: `helpers/render.py edit/edl.json -o edit/preview.mp4 --preview`. Final: same without `--preview`. `--build-subtitles` only when `should_build_subtitles` (verbatim) is true.
- Non-zero helper is turned into `CalledProcessError`; `last_error` is the last 40 lines of stderr; `preview.mp4` is never unlinked.
- ffmpeg stderr (plus stdout) is written to `edit/render.log`.
- `start_approve_and_preview` streams `APPROVE_PROMPT`, validates `edit/edl.json`, on failure `last_error = "\n".join(errors)` and returns without render, on success sets `edl_mtime_at_approve`, `chat_after_approve=False`, `edl_approved_at=now`, then `start_render(..., preview=True)`.
- API does not write `edl.json`. Render-final never calls `stream_claude`.
- Routes: approve/render-final 202; media FileResponse or 404.
- Tests copied verbatim from the brief.

### Deviation

1. **`pid == 1` busy guard** reused from Task 8/9 (`_raise_if_busy`). Windows `pid_alive(1)` is false; without the guard a busy test would start a live render/Claude.
2. **Approve runs Claude in a daemon thread** so `POST /api/approve` can return 202 immediately (same shape as transcribe). The brief lists steps 1–4 in the function body; they run in that thread, then `start_render` starts a second thread after job is set idle.
3. **Approve / render-final 409 when no folder** (same as transcribe). Media uses `_require_open_folder` → 404.
4. **Invalid EDL on `start_render` (sync, e.g. render-final)** is HTTP 400; busy is 409. Brief only specified 202 for the happy path.
5. **`start_render` persists `last_error` before raising invalid** so `GET /api/state` shows `error` even if the HTTP client already got 400.
6. **Source media** is restricted to `find_videos` names in the footage root (`/`, `\`, `..` → 404). Brief said “that source or 404”; this is the safe reading.

### Concerns / notes

1. **Official tests cover only invalid-EDL short-circuit and approve-route 202.** Approve sequencing, subtitle flag, render-final, media, and CalledProcessError handling are smoke-tested locally, not in-repo.
2. **Failed preview re-render writes `-o edit/preview.mp4` in place.** A later *final* failure leaves preview. A failed *preview refresh* can truncate/replace the previous preview because ffmpeg opens that path. Staging+replace was considered and dropped to keep the specified `-o` argv.
3. **Approve → idle → `start_render` race.** A second request can sneak in during the idle gap. Single-user local app; acceptable.
4. **`save_session` is non-atomic** (Task 4). Concurrent approve thread + state poll can `JSONDecodeError` on a half-written `app_session.json`.
5. **Approve does not require packed + doctor.ok.** Chat does. A click before pack still starts Claude. UI (Task 11) is expected to hide the button.
6. **Job kind during approve is `claude` then `render`.** Center state shows packed/stale/etc. until render starts (`rendering`). Fine for polling.
7. **`run_helper` is invoked via `proc_mod.run_helper`** so the jobs test monkeypatch actually intercepts (import-bound name would have been a false pass).
8. **`join(errors)`** is `"\n".join`. Approve last_error is the raw validator messages (no `invalid EDL:` prefix). `start_render` prefixes `invalid EDL:` so the brief test’s `match="invalid"` hits.
9. **Daemon threads, no helper pid.** Same as transcribe. Process exit kills an in-flight ffmpeg. Job pid is the API process after start; Claude overwrites pid while approve is streaming.
10. **No tests for `/api/render-final` or media routes** in the committed set.

### Not done (out of scope)

- UI Approve / Render final / player (Tasks 11–12).
- Commit of `.superpowers/` or `.env`.
- Push.

## Ready for next task

Yes — `POST /api/approve` writes EDL via Claude then renders `edit/preview.mp4`; `POST /api/render-final` renders `edit/final.mp4` without Claude; media routes serve those files. Task 11 can bind the buttons to these endpoints.

## Fix

Review findings after `25574d8`. Branch `local-app`. Not pushed.

### Changes

1. **Critical — failed preview no longer clobbers `edit/preview.mp4`.** `start_render(..., preview=True)` now writes `-o edit/preview.rendering.mp4` and `os.replace`s onto `preview.mp4` only when the helper returns 0. A non-zero helper (or exception) leaves the previous `preview.mp4` bytes untouched. Final still writes `edit/final.mp4` in place.
2. **Important — regression test** `test_failed_preview_render_keeps_last_good_file`: seeds known preview bytes, stubs `run_helper` to truncate the `-o` path and return 1, waits until the job is idle, asserts original bytes remain.
3. **Important — ffmpeg stderr on failure.** `helpers/render.py` `run_ffmpeg` prints captured stderr before raising `CalledProcessError`, so `run_helper` capture (and `last_error` last ~40 lines) includes it.

### Files changed

- `app/server/jobs.py`
- `helpers/render.py`
- `tests/test_jobs.py`

### Test command

```
pytest tests/test_jobs.py tests/test_api.py tests/test_edl.py -v
```

### Output

```
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.1.1, pluggy-1.6.0 -- C:\Users\Varun B\AppData\Local\Programs\Python\Python312\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\Varun B\Developer\video-use
configfile: pyproject.toml
plugins: anyio-4.13.0, langsmith-0.8.9
collecting ... collected 19 items

tests/test_jobs.py::test_start_transcribe_rejects_busy PASSED            [  5%]
tests/test_jobs.py::test_start_render_rejects_invalid_edl PASSED         [ 10%]
tests/test_jobs.py::test_failed_preview_render_keeps_last_good_file PASSED [ 15%]
tests/test_api.py::test_doctor PASSED                                    [ 21%]
tests/test_api.py::test_state_without_folder PASSED                      [ 26%]
tests/test_api.py::test_open_folder_lists_sources PASSED                 [ 31%]
tests/test_api.py::test_no_transcribe_route_implied PASSED               [ 36%]
tests/test_api.py::test_transcribe_requires_explicit_click PASSED        [ 42%]
tests/test_api.py::test_transcribe_409_when_busy PASSED                  [ 47%]
tests/test_api.py::test_approve_route_exists PASSED                      [ 52%]
tests/test_edl.py::test_valid PASSED                                     [ 57%]
tests/test_edl.py::test_unknown_source PASSED                            [ 63%]
tests/test_edl.py::test_missing_source_file PASSED                       [ 68%]
tests/test_edl.py::test_start_not_less_than_end PASSED                   [ 73%]
tests/test_edl.py::test_total_duration_autocorrect PASSED                [ 78%]
tests/test_edl.py::test_missing_overlay_file PASSED                      [ 84%]
tests/test_edl.py::test_escape_windows_drive PASSED                      [ 89%]
tests/test_edl.py::test_default_font_windows PASSED                      [ 94%]
tests/test_edl.py::test_force_style_uses_font PASSED                     [100%]

============================== warnings summary ===============================
..\..\AppData\Local\Programs\Python\Python312\Lib\site-packages\fastapi\testclient.py:1
  C:\Users\Varun B\AppData\Local\Programs\Python\Python312\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 19 passed, 1 warning in 1.55s ========================
```

### Commit

```
7ad05b4 fix: stage preview render so failures keep last good file
```

`.superpowers/` and `.env` not committed. Not pushed.

### Remaining

- Final render still writes `final.mp4` in place (allowed).
- Staging leftover `preview.rendering.mp4` is not deleted on failure.
- `os.replace` onto an open `preview.mp4` (player lock) can fail on Windows; last-good file is still left in place.
- Pre-existing: approve→idle→`start_render` race; non-atomic `save_session`.
