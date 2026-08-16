# Task 6 Report: center-state derivation

## Status

**Complete.** Branch `local-app`. Not pushed.

## What shipped

| File | Role |
|------|------|
| `app/server/state.py` | `CENTER_STATES`, `derive_center_state(folder, session)` |
| `tests/test_state.py` | Eight TDD tests per brief |

## Interfaces (verbatim)

```python
CENTER_STATES = (
    "empty", "inventory", "transcribing", "packed",
    "strategy-ready", "rendering", "preview-ready", "stale", "error",
)

def derive_center_state(folder: Path, session: dict) -> str
```

Priority (first match wins):

1. `job.kind == "transcribe"` → `transcribing`
2. `job.kind == "render"` → `rendering`
3. no folder / missing / no videos → `empty`
4. videos, no `edit/takes_packed.md` → `inventory`
5. `session["last_error"]` set → `error`
6. packed, no `edit/edl.json` → `packed`
7. EDL exists and (`chat_after_approve` or `edl_mtime > edl_mtime_at_approve + 0.001`) → `stale`
8. EDL not stale, no `preview.mp4` → `strategy-ready`
9. preview exists, not stale → `preview-ready`

`job.kind == "claude"` does not short-circuit; evaluation continues on files.

## TDD steps

1. Wrote `tests/test_state.py` exactly as brief.
2. `pytest tests/test_state.py -v` → collection **ERROR** (`ModuleNotFoundError: app.server.state`).
3. Implemented `app/server/state.py` from brief.
4. `pytest tests/test_state.py -v` → **8 passed**.
5. Committed.

## Commit

```
d8b6502 feat: derive review-panel center state
```

Files: `app/server/state.py`, `tests/test_state.py`.

## Test summary

```
tests/test_state.py::test_empty PASSED
tests/test_state.py::test_inventory PASSED
tests/test_state.py::test_transcribing PASSED
tests/test_state.py::test_packed PASSED
tests/test_state.py::test_error_after_pack PASSED
tests/test_state.py::test_strategy_ready PASSED
tests/test_state.py::test_stale_after_chat PASSED
tests/test_state.py::test_preview_ready PASSED
```

8 passed in ~0.08s.

## Self-review

### Matches brief

- Job kinds `transcribe` / `render` checked before disk inventory.
- Empty path uses `folder.exists()` and `find_videos`.
- Error only after packed exists (after inventory check).
- Stale uses `chat_after_approve` or mtime epsilon `+ 0.001`.
- Default `edl_mtime_at_approve=0` makes freshly written EDL stale until approve (documented intent).

### Concerns / notes

1. **No unit test for `rendering`** — brief implementation covers it; tests do not assert `job.kind == "render"`.
2. **`chat_after_approve` not in `default_session`** — relies on `session.get`; absent → falsy, fine for Task 6.
3. **`last_error` truthiness** — empty string is falsy; only non-empty errors flip to `error`.
4. **mtime epsilon 0.001** — protects float/filesystem resolution noise when approve sets mtime equal.
5. **Unapproved EDL → `stale`** — by design; approve flow (Tasks 8/9) must set `edl_mtime_at_approve` and clear `chat_after_approve`.

### Not done (out of scope)

- API/UI wiring of center state.
- Approve/render adapter setting mtime flags.
- Commit of `.superpowers/` or `.env`.
- Push.

## Ready for next task

Yes — center-state derivation is in place for the review panel.
