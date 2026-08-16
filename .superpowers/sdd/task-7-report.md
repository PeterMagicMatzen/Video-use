# Task 7 Report: FastAPI skeleton — doctor, folder, browse, state

## Status

**Complete.** Branch `local-app`. Not pushed.

## What shipped

| File | Role |
|------|------|
| `app/server/main.py` | FastAPI `app`, `CURRENT_FOLDER`, `project_payload()`, doctor/recents/folder/browse/state/open-edit |
| `app/__main__.py` | `python -m app` → uvicorn `127.0.0.1:8787` reload |
| `tests/test_api.py` | Four TDD tests per brief |

No transcribe route. Opening a folder does not create `takes_packed.md`.

## Interfaces (verbatim)

```
GET  /api/doctor          → run_doctor().to_dict()
GET  /api/recents         → { "recents": load_recents() }
POST /api/folder          body { "path": "C:\\..." } → mkdir edit/, add_recent, load_session, project_payload()
POST /api/folder/browse   → tkinter askdirectory; cancelled → { "cancelled": true }; else same as folder
GET  /api/state           → project_payload() or 404 { "detail": "no folder open" }
POST /api/open-edit       → os.startfile(str(folder / "edit")) on win32
```

`project_payload()` fields: `folder`, `doctor`, `sources`, `recents`, `center_state`, `error`, `packed_markdown`, `edl`, `has_preview`, `has_final`, `chat_enabled`, `job`, `stale`.

CORS: `http://localhost:5173`.

`CURRENT_FOLDER: Path | None` is process-global; `reset_current_folder()` for tests.

Doctor import: `sys.path` insert of `HELPERS` then `from doctor import run_doctor`.

## TDD steps

1. Wrote `tests/test_api.py` exactly as brief.
2. `pip install -e ".[app,dev]"` then `pytest tests/test_api.py -v` → collection **ERROR** (`ModuleNotFoundError: No module named 'app.server.main'`).
3. Implemented `app/__main__.py` (verbatim) and `app/server/main.py` (routes + specified snippets).
4. `pytest tests/test_api.py tests/test_state.py tests/test_session.py -v` → **16 passed**.
5. Committed.

## Commit

```
b286695 feat: FastAPI doctor and folder endpoints
```

Files: `app/server/main.py`, `app/__main__.py`, `tests/test_api.py`.

## Test summary

```
tests/test_api.py::test_doctor PASSED
tests/test_api.py::test_state_without_folder PASSED
tests/test_api.py::test_open_folder_lists_sources PASSED
tests/test_api.py::test_no_transcribe_route_implied PASSED
tests/test_state.py  — 8 passed
tests/test_session.py — 4 passed
```

16 passed (brief set) in ~4.29s. Full suite `pytest tests/ -v` → **34 passed**.

Starlette deprecation: `Using httpx with starlette.testclient is deprecated; install httpx2 instead.` — FastAPI/Starlette, not this task.

## Self-review

### Matches brief

- Routes listed above; no `/api/transcribe`.
- `POST /api/folder` creates `edit/`, calls `add_recent` + `load_session`, returns payload. Does not transcribe.
- `GET /api/state` 404 detail is `no folder open`.
- `chat_enabled` is packed-file exists **and** `doctor.ok` (fresh folder → False).
- CORS origin is exactly `http://localhost:5173`.
- Browse dialog is `pick_folder_dialog()` verbatim; not unit-tested.
- Tests copied verbatim from brief.

### Concerns / notes

1. **CORS origin is only `http://localhost:5173`.** Opening the UI at `http://127.0.0.1:5173` will fail CORS. Brief is explicit; Task 11 may need the extra origin if the Vite URL is 127.0.0.1.
2. **`GET /api/state` and `POST /api/folder` run live `run_doctor()` + `inventory()` (real ffprobe).** Tests accept that; doctor/inventory are slow (~1s+ per request) and depend on PATH/.env. Fine for local single-user; later polling every 1s (Task 11) will re-probe every source every tick.
3. **Invalid `edit/edl.json` → `edl: null`.** Malformed JSON is swallowed so state still loads. Center state still sees the file via `derive_center_state`.
4. **`load_session` on open does not persist `app_session.json`.** Matches brief (load only). First write happens in later job/session tasks.
5. **`POST /api/open-edit` 404 when no folder** and `{ "ok": true }` after `startfile` are not specified. 404 matches `/api/state`. Non-win32 is a no-op besides mkdir.
6. **Browse/open-edit/recents/payload-field tests absent** — brief: do not test the dialog; test only `/api/folder` plus doctor/state/no-transcribe.
7. **`CURRENT_FOLDER` is process-global, not thread-safe.** Acceptable for one-folder v1.
8. **`python -m app` needs repo root on `sys.path`.** `pyproject.toml` still has `py-modules = []` (pre-existing). Editable install + cwd work; a packaged install may not expose `app`.
9. **Missing/non-dir folder → 400 `folder not found`.** Not in brief; keeps `_open_folder` from treating a file as footage.

### Not done (out of scope)

- Transcribe / chat / media / approve / render routes (Tasks 8–12).
- Commit of `.superpowers/` or `.env`.
- Push.

## Ready for next task

Yes — FastAPI skeleton is in place for Task 8 (`POST /api/transcribe` + jobs) to extend `app/server/main.py`.
