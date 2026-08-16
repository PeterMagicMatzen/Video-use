# Final-review fix report

Commit: `50628f7` `fix: arm chat retry and cache-bust preview` on `local-app` (not pushed).

## Changes

- Chat stream now yields `{"error": ...}` on Claude failure, then `{"done": true}`.
- `streamChat` / `retryChat` throw on SSE `error` so `runChat` arms Retry.
- `project_payload()` includes `preview_mtime` from `edit/preview.mp4`; preview `<video>` src uses `?t=`.
- `claude_cmd` adds `--permission-mode acceptEdits` (not `--dangerously-skip-permissions`).

## pytest

```
pytest tests/test_claude.py tests/test_api.py tests/test_jobs.py -v
```

```
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.1.1, pluggy-1.6.0 -- C:\Users\Varun B\AppData\Local\Programs\Python\Python312\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\Varun B\Developer\video-use
configfile: pyproject.toml
plugins: anyio-4.13.0, langsmith-0.8.9
collecting ... collected 15 items

tests/test_claude.py::test_first_turn_has_no_resume PASSED               [  6%]
tests/test_claude.py::test_later_turn_resumes PASSED                     [ 13%]
tests/test_claude.py::test_parse_session_id PASSED                       [ 20%]
tests/test_api.py::test_doctor PASSED                                    [ 26%]
tests/test_api.py::test_state_without_folder PASSED                      [ 33%]
tests/test_api.py::test_open_folder_lists_sources PASSED                 [ 40%]
tests/test_api.py::test_no_transcribe_route_implied PASSED               [ 46%]
tests/test_api.py::test_transcribe_requires_explicit_click PASSED        [ 53%]
tests/test_api.py::test_transcribe_409_when_busy PASSED                  [ 60%]
tests/test_api.py::test_approve_route_exists PASSED                      [ 66%]
tests/test_api.py::test_preview_mtime_in_state PASSED                    [ 73%]
tests/test_api.py::test_chat_sse_error_event_on_failure PASSED           [ 80%]
tests/test_jobs.py::test_start_transcribe_rejects_busy PASSED            [ 86%]
tests/test_jobs.py::test_start_render_rejects_invalid_edl PASSED         [ 93%]
tests/test_jobs.py::test_failed_preview_render_keeps_last_good_file PASSED [100%]

============================== warnings summary ===============================
..\..\AppData\Local\Programs\Python\Python312\Lib\site-packages\fastapi\testclient.py:1
  C:\Users\Varun B\AppData\Local\Programs\Python\Python312\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 15 passed, 1 warning in 3.10s ========================
```

## npm test

From `app/web` (needed `Set-ExecutionPolicy -Scope Process Bypass` because Restricted policy blocks `npm.ps1`):

```
cd app/web
npm test
```

```
> web@0.0.0 test
> vitest run


 RUN  v4.1.10 C:/Users/Varun B/Developer/video-use/app/web

 ✓ src/centerState.test.ts (2 tests) 5ms
 ✓ src/api.test.ts (2 tests) 5ms

 Test Files  2 passed (2)
      Tests  4 passed (4)
   Start at  16:55:13
   Duration  290ms (transform 91ms, setup 0ms, import 129ms, tests 10ms, environment 0ms)
```
