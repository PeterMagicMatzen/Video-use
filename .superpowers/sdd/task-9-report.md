# Task 9 Report: Claude adapter

## Status

**Complete.** Branch `local-app`. Not pushed.

## What shipped

| File | Role |
|------|------|
| `app/server/claude.py` | `claude_cmd`, `parse_session_id`, `stream_claude`, `ensure_single_claude`, briefs |
| `app/server/main.py` | `POST /api/chat`, `/api/chat/retry`, `/api/reject` |
| `tests/test_claude.py` | first-turn argv, resume, `parse_session_id` (verbatim) |
| `SKILL.md` | local-app “do not transcribe/render” note after Hard Rules |

API does not write `edit/edl.json`. Approve/render stay Task 10.

## Interfaces (verbatim)

```python
CLAUDE_TIMEOUT_S = 600
EDITOR_BRIEF = """..."""   # exact brief text
APPROVE_PROMPT = """...""" # exported for Task 10; unused by these routes

def claude_cmd(*, folder: Path, session_id: str | None, prompt: str) -> list[str]
def parse_session_id(stream_line: str) -> str | None
def stream_claude(*, folder: Path, prompt: str, session: dict) -> Iterator[str]
def ensure_single_claude(session: dict) -> None
```

First turn (`session_id is None`):

```
claude -p --output-format stream-json --append-system-prompt <EDITOR_BRIEF>
  --allowedTools Read,Write,Edit,Glob,Grep
  --disallowedTools Bash,WebSearch,WebFetch,Agent
  --add-dir <folder> --add-dir <REPO_ROOT>
  <prompt>
```

Later turns add `--resume <id>`. Never `--continue`. Never `--dangerously-skip-permissions`.

```
POST /api/chat        body { "message": str } → 400 chat disabled; 409 busy;
                      SSE text/event-stream { "text": ... } then { "done": true };
                      sets chat_after_approve=True on success
POST /api/chat/retry  resend session["last_prompt"] with same session id
POST /api/reject      body { "note": str } → 200; next chat prepends the note
```

## TDD steps

1. Wrote `tests/test_claude.py` exactly as brief (including unused `pytest` import).
2. `pytest tests/test_claude.py -v` → collection **ERROR** (`ModuleNotFoundError: No module named 'app.server.claude'`).
3. Implemented `app/server/claude.py`, chat/retry/reject routes, SKILL.md note after Hard Rules.
4. `pytest tests/test_claude.py tests/test_api.py -v` → **9 passed**. Full suite **40 passed**.
5. Committed.

## Commit

```
4a67f4d feat: stream Claude editorial turns into the app
```

Files: `app/server/claude.py`, `app/server/main.py`, `tests/test_claude.py`, `SKILL.md`.

## Test summary

```
tests/test_claude.py::test_first_turn_has_no_resume PASSED
tests/test_claude.py::test_later_turn_resumes PASSED
tests/test_claude.py::test_parse_session_id PASSED
tests/test_api.py::test_doctor PASSED
tests/test_api.py::test_state_without_folder PASSED
tests/test_api.py::test_open_folder_lists_sources PASSED
tests/test_api.py::test_no_transcribe_route_implied PASSED
tests/test_api.py::test_transcribe_requires_explicit_click PASSED
tests/test_api.py::test_transcribe_409_when_busy PASSED
```

9 passed (brief set) in ~1.01s. Full suite `pytest tests/ -v` → **40 passed**.

Starlette deprecation: `Using httpx with starlette.testclient is deprecated; install httpx2 instead.` — FastAPI/Starlette, not this task.

## Self-review

### Matches brief

- `claude_cmd` argv matches the specified first/later turn shapes. Bash is only on `--disallowedTools`. Tools allowed: Read,Write,Edit,Glob,Grep.
- `parse_session_id` returns top-level `session_id` (system init + result) or `None` for non-JSON.
- `stream_claude` uses `Popen`, line-buffered stdout, `env=helper_env()`, `cwd=folder`, 600s timeout + kill, yields assistant `message.content[].text` plus `delta`/`partial` text, `save_session`s `claude_session_id` as soon as it appears, `RuntimeError` on non-zero.
- `ensure_single_claude` raises `RuntimeError("busy")` when `job.kind == "claude"`.
- Chat: 400 if not packed+doctor.ok; 409 if busy; SSE then `{done: true}`; `chat_after_approve=True` after a successful non-approve turn.
- Retry resends `last_prompt` into the same `claude_session_id` (`--resume`).
- Reject stores `pending_note` (200). Next chat prepends `{note}\n\n{message}` and clears the note.
- API never writes `edl.json`. `APPROVE_PROMPT` is defined only.
- SKILL.md note is the exact paragraph, placed after the Hard Rules list.
- Tests copied verbatim from the brief.

### Deviation

1. **`pid == 1` busy guard** on chat (same Windows issue as Task 8). `load_session` reclaims pid 1 as dead here; the route treats persisted `pid==1` + non-idle kind as busy *before* reclaim. Needed so a later pid=1 busy test does not start a live `claude.exe`.
2. **Chat 404 when no folder** (not specified). Transcribe uses 409 for that case; state uses 404. Chat follows state.
3. **SKILL.md location** is after Hard Rules (Step 3 exact text), not also at the top of “The process” (Files blurb).
4. **Nested `event.delta` / `event.partial`** also yielded, in addition to top-level keys. Extra, backward-compatible.

### Concerns / notes

1. **Official tests cover argv + parse only.** Routes, timeout, non-zero, and `ensure_single_claude` are untested in-repo. Smoke-tested locally with a fake `Popen` and a mocked `stream_claude` (400/409/SSE/reject/retry). Not committed.
2. **`_chat_enabled` hits live `run_doctor()`** on every chat/retry. This machine is green. A machine with a failed doctor check gets 400 even if packed exists — that is the spec.
3. **Token granularity.** Argv is exactly as specified (`--output-format stream-json` only). Claude may emit full assistant messages rather than token deltas unless the CLI adds partials. UI (Task 12) still appends whatever `ev.text` arrives.
4. **Mid-stream failure** sets `last_error` and still sends `{done: true}`. No `{error}` SSE field (Task 12 only reads `ev.text`). Session id is kept for Retry.
5. **`chat_after_approve` is set only on a clean finish**, not on timeout/non-zero. Failed turns do not flip center state to stale.
6. **Job pid** starts as `os.getpid()`, then `stream_claude` overwrites with the Claude pid. Reclaim after API crash sees a dead Claude pid.
7. **One-at-a-time** is per open folder via `job.kind`. Reject is allowed while busy (only stores a note).
8. **`last_prompt` includes a prepended reject note**, so Retry resends the same combined prompt (does not prepend again).
9. **`HELPERS` is not imported in `claude.py`.** `--add-dir REPO_ROOT` covers the skill/helpers; env comes from `helper_env()`.
10. **No `edit/claude.log`.** stderr is only used for the non-zero `RuntimeError` (last 400 chars).
11. **Duplicate `_now` / `_persisted_job`** with `jobs.py` — not asked to merge.
12. **`tests/test_claude.py` unused `pytest` import** — copied from the brief.

### Not done (out of scope)

- Approve / preview / final render (Task 10). `APPROVE_PROMPT` is unused by routes.
- UI SSE consumer (Task 12).
- Commit of `.superpowers/` or `.env`.
- Push.

## Ready for next task

Yes — Task 10 can import `stream_claude` + `APPROVE_PROMPT` and add `/api/approve` without the API writing `edl.json` itself.
