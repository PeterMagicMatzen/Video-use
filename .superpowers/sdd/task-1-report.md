# Task 1 Report: UTF-8 stdio + pytest harness

## Status

**DONE_WITH_CONCERNS** — implementation complete and committed; one intentional conftest deviation (see Issues).

## What was implemented

1. **`pyproject.toml`** — optional-deps expanded to:
   - `animations = ["manim"]`
   - `app = ["fastapi>=0.115", "uvicorn[standard]>=0.32", "pydantic>=2.0"]`
   - `dev = ["pytest>=8.0"]`

2. **`helpers/stdio.py`** — `configure_stdio() -> None` reconfigures `sys.stdout` and `sys.stderr` to UTF-8 with `errors="replace"` when `reconfigure` is available.

3. **Helper `main()` hooks** — local import + call at top of `main()` in:
   - `helpers/render.py`
   - `helpers/grade.py`
   - `helpers/pack_transcripts.py`
   - `helpers/transcribe.py`
   - `helpers/transcribe_batch.py`

4. **Pytest harness**
   - `tests/conftest.py` — path setup for repo root + `helpers/`
   - `tests/test_stdio.py` — cp1252 stdout arrow print regression test

## What was tested and results

| Command | Result |
|---------|--------|
| `pip install -e ".[dev]"` | Success (pytest already present / reinstalled editable) |
| `pytest tests/test_stdio.py -v` (RED, before `stdio.py`) | ERROR: `ModuleNotFoundError: No module named 'stdio'` |
| `pytest tests/test_stdio.py -v` (GREEN, after impl) | **1 passed** |
| `pytest -v` (full suite before commit) | **1 passed** |

### TDD Evidence

**RED** — after test + pyproject only, no `helpers/stdio.py`:

```
pytest tests/test_stdio.py -v
...
tests\test_stdio.py:6: in <module>
    from stdio import configure_stdio
E   ModuleNotFoundError: No module named 'stdio'
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
============================== 1 error in 0.22s ===============================
```

**GREEN** — after `stdio.py`, helper hooks, and collection-time path in conftest:

```
pytest tests/test_stdio.py -v
...
tests/test_stdio.py::test_configure_stdio_allows_arrows_on_cp1252 PASSED [100%]
============================== 1 passed in 0.01s ==============================
```

Full suite:

```
pytest -v
...
tests/test_stdio.py::test_configure_stdio_allows_arrows_on_cp1252 PASSED [100%]
============================== 1 passed in 0.02s ==============================
```

## Files changed

| File | Action |
|------|--------|
| `pyproject.toml` | Modified — app + dev optional deps |
| `helpers/stdio.py` | Created |
| `helpers/render.py` | Modified — `configure_stdio()` in `main()` |
| `helpers/grade.py` | Modified — same |
| `helpers/pack_transcripts.py` | Modified — same |
| `helpers/transcribe.py` | Modified — same |
| `helpers/transcribe_batch.py` | Modified — same |
| `tests/conftest.py` | Created (see deviation below) |
| `tests/test_stdio.py` | Created |

**Not modified (per brief):** `helpers/timeline_view.py`

## Commit

- `fd326d8` — `fix: utf-8 helper stdout on Windows`
- Branch: `local-app`
- Not pushed

## Self-review

### Completeness

- [x] pytest `dev` extra and planned `app` extra in `pyproject.toml`
- [x] `configure_stdio()` matches brief
- [x] All five specified helpers call it at start of `main()` via local import
- [x] Test asserts arrow survives cp1252→reconfigure→UTF-8 path
- [x] Committed with requested message and file set

### Quality / discipline (YAGNI)

- Implementation is minimal; no extra APIs or packages beyond the brief.
- Local import pattern preserved so `python helpers/<script>.py` works with `helpers/` on `sys.path[0]`.

### Testing

- Real behavior: monkeypatched `TextIOWrapper(encoding="cp1252")`, then reconfigure + print + decode buffer as UTF-8.
- TDD: RED (`ModuleNotFoundError`) then GREEN.
- Output pristine (pass).

## Issues or concerns

1. **conftest path timing (deviation):** The brief’s fixture-only `helpers_on_path` runs *after* collection. Top-level `from stdio import configure_stdio` in `test_stdio.py` therefore still fails with `ModuleNotFoundError` even after `helpers/stdio.py` exists. Added **module-level** `sys.path` inserts in `tests/conftest.py` (fixture kept) so collection can import helpers. Without this, Step 5 cannot pass as written.

2. **`timeline_view.py`:** Has a `main()` but was not in the task file list; left unchanged. Later tasks may want the same hook if it prints non-ASCII.

3. **`app` optional deps:** Added now per brief though unused until later tasks; no runtime impact.
