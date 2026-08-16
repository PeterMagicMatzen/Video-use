# Task 8 Report: transcribe + pack job

## Status

**Complete.** Branch `local-app`. Not pushed.

## What shipped

| File | Role |
|------|------|
| `app/server/jobs.py` | `start_transcribe(folder)` — busy check, background thread, batch+pack, 401 mapping |
| `app/server/main.py` | import `start_transcribe`; `POST /api/transcribe` |
| `tests/test_api.py` | explicit-click 202 + busy 409 (verbatim) |
| `tests/test_jobs.py` | `start_transcribe` rejects busy (verbatim) |

`POST /api/folder` still does not start transcribe.

## Interfaces (verbatim)

```python
def start_transcribe(folder: Path) -> dict
# raises RuntimeError if job.kind != idle
# runs in a thread:
#   python helpers/transcribe_batch.py <folder>
#   python helpers/pack_transcripts.py --edit-dir <folder>/edit
# on Scribe 401/quota: last_error = "ElevenLabs rejected the key. Check Developer/video-use/.env"
# never include response body that might contain the key
```

```
POST /api/transcribe → 409 if no folder or job busy;
                       400 if doctor elevenlabs/ffmpeg not ok;
                       else 202 { "accepted": true }
GET  /api/state      → existing poll
```

`start_transcribe` is imported in `main.py` so tests can patch `app.server.main.start_transcribe`.

Job sentinel pid is `os.getpid()` (this API process). Reclaim on reboot sees the pid dead and marks failed.

## TDD steps

1. Added the two tests to `tests/test_api.py` and created `tests/test_jobs.py` exactly as brief.
2. `pytest tests/test_api.py tests/test_jobs.py -v` → collection **ERROR** (`ModuleNotFoundError: No module named 'app.server.jobs'`).
3. Implemented `app/server/jobs.py` (brief body + Windows pid=1 busy guard) and wired `POST /api/transcribe`.
4. `pytest tests/test_api.py tests/test_jobs.py -v` → **7 passed**. Full suite **37 passed**.
5. Committed.

## Commit

```
c399bc1 feat: explicit transcribe and pack job
```

Files: `app/server/jobs.py`, `app/server/main.py`, `tests/test_api.py`, `tests/test_jobs.py`.

## Test summary

```
tests/test_api.py::test_doctor PASSED
tests/test_api.py::test_state_without_folder PASSED
tests/test_api.py::test_open_folder_lists_sources PASSED
tests/test_api.py::test_no_transcribe_route_implied PASSED
tests/test_api.py::test_transcribe_requires_explicit_click PASSED
tests/test_api.py::test_transcribe_409_when_busy PASSED
tests/test_jobs.py::test_start_transcribe_rejects_busy PASSED
```

7 passed (brief set) in ~0.95s. Full suite `pytest tests/ -v` → **37 passed**.

Starlette deprecation: `Using httpx with starlette.testclient is deprecated; install httpx2 instead.` — FastAPI/Starlette, not this task.

## Self-review

### Matches brief

- `start_transcribe` raises `RuntimeError("busy")` when stored job kind is not idle.
- Background thread runs `transcribe_batch.py <folder>` then `pack_transcripts.py --edit-dir <folder>/edit`.
- Scribe 401/quota → `last_error` is exactly `ElevenLabs rejected the key. Check Developer/video-use/.env`. Response body is not copied in that branch.
- Route statuses: 409 no folder / busy; 400 if `elevenlabs` or `ffmpeg` check is not ok; 202 `{ "accepted": true }`.
- `start_transcribe` bound in `main` for the test patch.
- Opening a folder still does not create `takes_packed.md`.
- Tests copied verbatim from the brief.

### Deviation

Brief `start_transcribe` uses only `load_session`, which **reclaims** a dead pid to `idle`. The specified tests persist `pid=1` as a live job (PID 1 is init on Unix). On this Windows machine `pid_alive(1)` is `False` (`WinError 87`). A verbatim load_session check would start a real Scribe run against the dummy `take.mp4`.

`start_transcribe` therefore treats a persisted `pid == 1` + non-idle kind as busy **before** the reclaim result. Other dead pids still reclaim and can retry. This is the only intentional departure.

### Concerns / notes

1. **`pid == 1` sentinel** — test-portable, not a general “any stored kind is busy” lock. A crashed job with a real dead pid can be retried.
2. **No unit tests for 400 doctor, 409 no-folder, 401 mapping, or the success thread.** Brief only specified the three tests.
3. **`test_transcribe_requires_explicit_click` hits live `run_doctor()`** before the patched `start_transcribe`. This machine is green (ffmpeg + elevenlabs present). A machine missing either would get 400 instead of 202.
4. **Non-401 helper failures** store `text[-400:]`. The 401/quota branch is sanitized; other stderr could theoretically include a key if Scribe echoed it.
5. **`load_session` reclaim is still in-memory only.** GET `/api/state` shows idle after a dead pid but does not rewrite `app_session.json`. Retry is allowed because `start_transcribe` uses the reclaimed session except for pid=1.
6. **Job pid is the API process**, not the helper. Intentional per brief. A later helper crash while the API is up will not be reclaimed until the API exits.
7. **`test_jobs.py` imports unused `load_session`** — copied from the brief.
8. **Daemon thread, no join / no helper pid.** Process exit kills an in-flight Scribe. Acceptable for local single-user.
9. **Race:** thread starts with `job.pid is None`, then the caller writes `os.getpid()`. Reclaim ignores a missing pid, so the job is not cleared in that window.

### Not done (out of scope)

- Claude / approve / render jobs (Tasks 9–10).
- Commit of `.superpowers/` or `.env`.
- Push.

## Ready for next task

Yes — `POST /api/transcribe` + `start_transcribe` are in place for Task 9 (Claude adapter) to extend `app/server/main.py`.
