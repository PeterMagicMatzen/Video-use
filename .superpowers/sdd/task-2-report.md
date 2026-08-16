# Task 2 Report: doctor command

## Status

**DONE**

## Summary

Implemented `helpers/doctor.py` preflight checks (ffmpeg, ffprobe, libass/subtitles filter, claude CLI, ElevenLabs API key) with injectable dependencies for tests, plus `tests/test_doctor.py`. Followed TDD: failing import, then implementation matching the brief verbatim.

## Files created

| Path | Role |
|------|------|
| `helpers/doctor.py` | `Check`, `DoctorReport`, `run_doctor()`, `main()` CLI |
| `tests/test_doctor.py` | Four unit tests with injected `which` / `run` / `key_loader` |

## Interfaces

### Produced

```python
@dataclass
class Check:
    name: str       # "ffmpeg" | "ffprobe" | "libass" | "claude" | "elevenlabs"
    ok: bool
    detail: str     # never contains a secret
    required: bool

@dataclass
class DoctorReport:
    checks: list[Check]
    # ok: property — True iff every required check is ok
    def to_dict(self) -> dict: ...

def run_doctor(
    *,
    which=shutil.which,
    run=subprocess.run,
    key_loader=_load_key_from_env_files,
) -> DoctorReport: ...

def main() -> None: ...  # configure_stdio(); print checks; exit 0/1
```

### Consumed

- `configure_stdio()` from `helpers/stdio.py` (Task 1), called at the start of `main()`.

## Behavior

1. **PATH tools:** `ffmpeg`, `ffprobe`, `claude` via `which`; detail is path or `"not on PATH"`.
2. **libass:** if ffmpeg present, `ffmpeg -hide_banner -filters`; regex looks for a `subtitles` filter line; else `"ffmpeg missing"`.
3. **elevenlabs:** `key_loader()`; detail is `"present"` or missing message — **never** the key value.
4. **Report.ok:** `all(c.ok for c in checks if c.required)` (all five checks are required).
5. **Key loading (default):** repo-root `.env` then cwd `.env` for `ELEVENLABS_API_KEY`, else `os.environ`.

## TDD steps executed

1. Wrote `tests/test_doctor.py` as specified.
2. `pytest tests/test_doctor.py -v` → `ModuleNotFoundError: No module named 'doctor'`.
3. Implemented `helpers/doctor.py` as specified.
4. `pytest tests/test_doctor.py -v` → **4 passed**.
5. Full suite `pytest tests/ -v` → **5 passed** (includes Task 1 stdio).
6. Commit: `feat: add helpers/doctor.py preflight`.

## Tests

```
tests/test_doctor.py::test_all_required_ok PASSED
tests/test_doctor.py::test_missing_ffmpeg_fails PASSED
tests/test_doctor.py::test_missing_key_fails_without_echo PASSED
tests/test_doctor.py::test_libass_absent PASSED
tests/test_stdio.py::test_configure_stdio_allows_arrows_on_cp1252 PASSED
```

**4/4 doctor tests pass; 5/5 full suite pass.**

## Commit

- **SHA:** `10c4165`
- **Subject:** `feat: add helpers/doctor.py preflight`
- **Branch:** `local-app` (not pushed)
- **Files in commit:** `helpers/doctor.py`, `tests/test_doctor.py` only
- **Not committed:** `.env`, `.superpowers/`

## Self-review

### Matches brief

- [x] Dataclasses and injectable `run_doctor` signature
- [x] Secret never appears in `detail` (asserted with `"sk-test"`)
- [x] Missing key detail contains `"missing"`
- [x] libass failure when subtitles filter absent
- [x] Missing ffmpeg fails report and marks ffmpeg required
- [x] `main()` calls `configure_stdio()` first
- [x] Import style `from stdio import configure_stdio`
- [x] Commit message and file set exact

### Minor notes (not blocking)

- Test file includes unused `Path` import and unused `_which_missing` helper; kept for brief fidelity.
- Check order is ffmpeg → ffprobe → claude → libass → elevenlabs; tests use set equality on names, so order is unconstrained by tests.
- No `pyproject.toml` console_scripts entry for `doctor` — out of scope for this task.
- Real `subprocess.run` for libass is only exercised when ffmpeg is on PATH (CLI path); unit tests inject `run`.

### Security

- Key values never printed or stored in check details.
- `.env` not staged or committed.

## Concerns

None for functionality or task scope.

## Report path

`C:\Users\Varun B\Developer\video-use\.superpowers\sdd\task-2-report.md`
