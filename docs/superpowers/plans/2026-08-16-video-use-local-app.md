# video-use Local App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a local website on this Windows machine that transcribes talking-head takes, chats a strategy through Claude Code, and renders `edit/preview.mp4` / `edit/final.mp4` without the user touching a terminal after launch.

**Architecture:** Vite/React on `:5173` talks only to a FastAPI control plane on `:8787`. The API owns doctor, inventory, transcribe, pack, and render. Claude Code (`claude -p --resume`) is editorial only: it reads `edit/takes_packed.md` and writes `edit/edl.json` after an Approve click. `edit/` is the source of truth.

**Tech Stack:** Python 3.10+, FastAPI, uvicorn, pydantic, existing `helpers/` scripts, Vite + React + TypeScript, Claude Code CLI, ffmpeg/ffprobe, ElevenLabs Scribe.

## Global Constraints

- Work on git branch `local-app`. Never push to `origin` (`browser-use/video-use`).
- One footage folder at a time. Product name is "video-use local app" — do not invent a second name.
- UI `localhost:5173`, API `localhost:8787`.
- Transcribe starts only on an explicit **Transcribe** click. Never auto-start Scribe.
- Claude must not run Bash or any web/network tool. No `--dangerously-skip-permissions`.
- Later Claude turns always `--resume <id>` stored in `edit/app_session.json`. Do not use `--continue`.
- `.env` / API keys never go to the browser. UI sees only `present` | `missing` | `rejected`.
- Every helper subprocess env must set `PYTHONIOENCODING=utf-8` and `PYTHONUTF8=1`.
- Helpers stay in `helpers/` and are imported or subprocessed from there — never copied into `app/`.
- Recents and app logs live under `%USERPROFILE%\.video-use\`. Footage `edit/` stays next to the sources.
- Video extensions: `.mp4`, `.mov`, `.mkv`, `.m4v`, `.webm`, `.avi` (case-insensitive).
- TDD: failing test, then minimal code, then commit. Do not commit `.env`.

---

## File map

| Path | Responsibility |
|---|---|
| `helpers/stdio.py` | `configure_stdio()` — UTF-8 stdout/stderr |
| `helpers/doctor.py` | Binary + key checks; CLI + importable `run_doctor()` |
| `helpers/edl.py` | `validate_edl()`, `escape_subtitles_path()`, `default_subtitle_font()`, `force_style()` |
| `helpers/render.py` | Use `edl.py` for path escape + font; call `configure_stdio()` |
| `helpers/grade.py` | Call `configure_stdio()` at `main()` |
| `helpers/pack_transcripts.py` | Call `configure_stdio()` at `main()` |
| `helpers/transcribe.py` | Call `configure_stdio()` at `main()` |
| `helpers/transcribe_batch.py` | Call `configure_stdio()` at `main()`; accept `.webm` |
| `helpers/SKILL.md` | N/A — skill file is repo-root `SKILL.md` |
| `SKILL.md` | Add: when driven by the local app, do not transcribe or render |
| `install.md` | Windows section |
| `pyproject.toml` | extras `[app]` and `[dev]` |
| `app/__init__.py` | empty |
| `app/__main__.py` | start uvicorn (dev launcher also starts Vite) |
| `app/scripts/dev.ps1` | start API + Vite |
| `app/server/paths.py` | `REPO_ROOT`, `HELPERS`, `APP_HOME` |
| `app/server/proc.py` | `helper_env()`, `run_helper()` |
| `app/server/session.py` | load/save `edit/app_session.json`, reclaim dead jobs |
| `app/server/recents.py` | `%USERPROFILE%\.video-use\recents.json` |
| `app/server/inventory.py` | ffprobe source list |
| `app/server/state.py` | `derive_center_state()`, `ProjectState` |
| `app/server/claude.py` | start/resume/stream Claude; briefs |
| `app/server/jobs.py` | transcribe + render background jobs |
| `app/server/main.py` | FastAPI routes |
| `app/web/` | Vite React UI |
| `tests/conftest.py` | `repo_root`, `helpers_on_path` |
| `tests/test_stdio.py` | UTF-8 arrows |
| `tests/test_doctor.py` | doctor fakes |
| `tests/test_edl.py` | validator + path escape + font |
| `tests/test_session.py` | session file + dead pid |
| `tests/test_inventory.py` | extension filter + ffprobe parse |
| `tests/test_state.py` | center-state table |
| `tests/test_claude.py` | argv + session id parse + one-at-a-time |
| `tests/test_api.py` | folder / doctor / validate / no-auto-transcribe |
| `app/web/src/state.test.ts` | mirrors server states if any client mapping remains |

---

### Task 1: UTF-8 stdio + pytest harness

**Files:**
- Create: `helpers/stdio.py`
- Create: `tests/conftest.py`
- Create: `tests/test_stdio.py`
- Modify: `pyproject.toml`
- Modify: `helpers/render.py` (top of `main()`)
- Modify: `helpers/grade.py` (top of `main()`)
- Modify: `helpers/pack_transcripts.py` (top of `main()`)
- Modify: `helpers/transcribe.py` (top of `main()`)
- Modify: `helpers/transcribe_batch.py` (top of `main()`)

**Interfaces:**
- Consumes: nothing
- Produces: `configure_stdio() -> None` in `helpers/stdio.py`

- [ ] **Step 1: Add pytest extra**

In `pyproject.toml`, replace the optional-deps block with:

```toml
[project.optional-dependencies]
animations = ["manim"]
app = ["fastapi>=0.115", "uvicorn[standard]>=0.32", "pydantic>=2.0"]
dev = ["pytest>=8.0"]
```

- [ ] **Step 2: Write the failing test**

`tests/conftest.py`:

```python
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HELPERS = REPO_ROOT / "helpers"


@pytest.fixture(autouse=True)
def helpers_on_path():
    for p in (str(REPO_ROOT), str(HELPERS)):
        if p not in sys.path:
            sys.path.insert(0, p)
    yield
```

`tests/test_stdio.py`:

```python
from __future__ import annotations

import io
import sys

from stdio import configure_stdio


def test_configure_stdio_allows_arrows_on_cp1252(monkeypatch):
    buf = io.BytesIO()
    fake = io.TextIOWrapper(buf, encoding="cp1252", errors="strict", write_through=True)
    monkeypatch.setattr(sys, "stdout", fake)
    configure_stdio()
    print("extracting 1 segment(s) → clips/")
    fake.flush()
    assert "→" in buf.getvalue().decode("utf-8")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pip install -e ".[dev]"` then `pytest tests/test_stdio.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'stdio'`

- [ ] **Step 4: Implement `configure_stdio` and call it from every helper `main()`**

`helpers/stdio.py`:

```python
"""Make helper prints safe on non-UTF-8 stdout (Windows cp1252)."""

from __future__ import annotations

import sys


def configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")
```

At the first line of `main()` in `render.py`, `grade.py`, `pack_transcripts.py`, `transcribe.py`, `transcribe_batch.py`:

```python
    from stdio import configure_stdio
    configure_stdio()
```

Use a local import so running a helper as a script still works (`helpers/` is on `sys.path[0]`).

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_stdio.py -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml helpers/stdio.py helpers/render.py helpers/grade.py helpers/pack_transcripts.py helpers/transcribe.py helpers/transcribe_batch.py tests/conftest.py tests/test_stdio.py
git commit -m "fix: utf-8 helper stdout on Windows"
```

---

### Task 2: doctor command

**Files:**
- Create: `helpers/doctor.py`
- Create: `tests/test_doctor.py`

**Interfaces:**
- Consumes: `configure_stdio()` from Task 1
- Produces: `run_doctor(*, which, run, key_loader) -> DoctorReport` where

```python
@dataclass
class Check:
    name: str          # "ffmpeg" | "ffprobe" | "libass" | "claude" | "elevenlabs"
    ok: bool
    detail: str        # never contains a secret
    required: bool

@dataclass
class DoctorReport:
    checks: list[Check]
    ok: bool           # True iff every required check is ok
```

`key_loader` returns `""` or a non-empty string. `run_doctor` must not put the key in `detail`.

- [ ] **Step 1: Write the failing tests**

`tests/test_doctor.py`:

```python
from __future__ import annotations

from pathlib import Path

from doctor import run_doctor


def _which_ok(name: str):
    return f"C:/tools/{name}.exe"


def _which_missing(name: str):
    return None


def _run_filters(*_a, **_k):
    class R:
        stdout = " T. subtitles     A V  Subtitle filter\n"
        returncode = 0
    return R()


def test_all_required_ok():
    report = run_doctor(which=_which_ok, run=_run_filters, key_loader=lambda: "sk-test")
    assert report.ok
    assert {c.name for c in report.checks} == {"ffmpeg", "ffprobe", "libass", "claude", "elevenlabs"}
    assert all(c.ok for c in report.checks)
    assert all("sk-test" not in c.detail for c in report.checks)


def test_missing_ffmpeg_fails():
    def which(name: str):
        return None if name == "ffmpeg" else _which_ok(name)
    report = run_doctor(which=which, run=_run_filters, key_loader=lambda: "x")
    assert not report.ok
    ffmpeg = next(c for c in report.checks if c.name == "ffmpeg")
    assert ffmpeg.ok is False
    assert ffmpeg.required is True


def test_missing_key_fails_without_echo():
    report = run_doctor(which=_which_ok, run=_run_filters, key_loader=lambda: "")
    key = next(c for c in report.checks if c.name == "elevenlabs")
    assert key.ok is False
    assert "missing" in key.detail.lower()


def test_libass_absent():
    class R:
        stdout = " T. scale         V  Scale\n"
        returncode = 0
    report = run_doctor(which=_which_ok, run=lambda *a, **k: R(), key_loader=lambda: "x")
    libass = next(c for c in report.checks if c.name == "libass")
    assert libass.ok is False
    assert libass.required is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_doctor.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'doctor'`

- [ ] **Step 3: Implement `helpers/doctor.py`**

```python
"""Preflight: ffmpeg, ffprobe, libass, claude, ElevenLabs key."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

from stdio import configure_stdio


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    required: bool


@dataclass
class DoctorReport:
    checks: list[Check]

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks if c.required)

    def to_dict(self) -> dict:
        return {"ok": self.ok, "checks": [asdict(c) for c in self.checks]}


def _load_key_from_env_files() -> str:
    repo_env = Path(__file__).resolve().parent.parent / ".env"
    for candidate in (repo_env, Path(".env")):
        if not candidate.exists():
            continue
        for line in candidate.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() == "ELEVENLABS_API_KEY":
                return v.strip().strip('"').strip("'")
    return os.environ.get("ELEVENLABS_API_KEY", "")


def run_doctor(*, which=shutil.which, run=subprocess.run, key_loader=_load_key_from_env_files) -> DoctorReport:
    checks: list[Check] = []
    for name in ("ffmpeg", "ffprobe", "claude"):
        path = which(name)
        checks.append(Check(name=name, ok=bool(path), detail=path or "not on PATH", required=True))

    ffmpeg = which("ffmpeg")
    if ffmpeg:
        proc = run(
            [ffmpeg, "-hide_banner", "-filters"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        has_subs = bool(re.search(r"^\s*\S+\s+subtitles\s", proc.stdout or "", re.M))
        checks.append(Check(
            name="libass",
            ok=has_subs,
            detail="subtitles filter present" if has_subs else "ffmpeg has no subtitles/libass filter",
            required=True,
        ))
    else:
        checks.append(Check(name="libass", ok=False, detail="ffmpeg missing", required=True))

    key = key_loader() or ""
    checks.append(Check(
        name="elevenlabs",
        ok=bool(key.strip()),
        detail="present" if key.strip() else "missing — set ELEVENLABS_API_KEY in Developer/video-use/.env",
        required=True,
    ))
    return DoctorReport(checks=checks)


def main() -> None:
    configure_stdio()
    argparse.ArgumentParser(description="Check video-use dependencies").parse_args()
    report = run_doctor()
    for c in report.checks:
        mark = "ok" if c.ok else "FAIL"
        print(f"{mark:4}  {c.name:12}  {c.detail}")
    sys.exit(0 if report.ok else 1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_doctor.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add helpers/doctor.py tests/test_doctor.py
git commit -m "feat: add helpers/doctor.py preflight"
```

---

### Task 3: EDL validator, subtitle path escape, Windows font

**Files:**
- Create: `helpers/edl.py`
- Create: `tests/test_edl.py`
- Modify: `helpers/render.py` (replace inline path escape and `SUB_FORCE_STYLE` font)

**Interfaces:**
- Consumes: nothing from Tasks 1–2
- Produces:
  - `validate_edl(edl: dict, *, edit_dir: Path) -> ValidationResult`
  - `ValidationResult(ok: bool, errors: list[str], warnings: list[str], edl: dict)` — `edl` is a copy with `total_duration_s` auto-corrected when off by more than 0.05s
  - `escape_subtitles_path(path: Path) -> str`
  - `default_subtitle_font() -> str` — `"Arial"` on `sys.platform == "win32"`, else `"Helvetica"`
  - `force_style(*, font: str | None = None, extra: str | None = None) -> str`

Validation rules (all errors unless noted):

- `sources` must be a dict and `ranges` a non-empty list
- every `ranges[].source` is a key in `sources`
- every source path exists (absolute, or resolved relative to `edit_dir`)
- `start` and `end` are numbers, `start >= 0`, `end > start`
- if `overlays` is a non-empty list, each item has `file` that exists (resolved vs `edit_dir`)
- `total_duration_s` missing or `|value - sum(end-start)| > 0.05` → warning, set `edl["total_duration_s"] = sum`
- unknown keys ignored

- [ ] **Step 1: Write the failing tests**

`tests/test_edl.py`:

```python
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from edl import default_subtitle_font, escape_subtitles_path, force_style, validate_edl


def _edl(tmp: Path, **over):
    src = tmp / "C0103.MP4"
    src.write_bytes(b"x")
    base = {
        "version": 1,
        "sources": {"C0103": str(src)},
        "ranges": [{"source": "C0103", "start": 2.42, "end": 6.85, "beat": "HOOK", "quote": "x", "reason": "y"}],
        "grade": "none",
        "overlays": [],
        "total_duration_s": 4.43,
    }
    base.update(over)
    return base


def test_valid(tmp_path: Path):
    result = validate_edl(_edl(tmp_path), edit_dir=tmp_path)
    assert result.ok
    assert result.errors == []


def test_unknown_source(tmp_path: Path):
    edl = _edl(tmp_path)
    edl["ranges"][0]["source"] = "NOPE"
    result = validate_edl(edl, edit_dir=tmp_path)
    assert not result.ok
    assert any("NOPE" in e for e in result.errors)


def test_missing_source_file(tmp_path: Path):
    edl = _edl(tmp_path)
    edl["sources"]["C0103"] = str(tmp_path / "missing.mp4")
    result = validate_edl(edl, edit_dir=tmp_path)
    assert not result.ok


def test_start_not_less_than_end(tmp_path: Path):
    edl = _edl(tmp_path)
    edl["ranges"][0]["start"] = 6.85
    edl["ranges"][0]["end"] = 2.42
    result = validate_edl(edl, edit_dir=tmp_path)
    assert not result.ok


def test_total_duration_autocorrect(tmp_path: Path):
    edl = _edl(tmp_path, total_duration_s=99.0)
    result = validate_edl(edl, edit_dir=tmp_path)
    assert result.ok
    assert result.warnings
    assert result.edl["total_duration_s"] == pytest.approx(4.43, abs=0.001)


def test_missing_overlay_file(tmp_path: Path):
    edl = _edl(tmp_path, overlays=[{"file": "animations/slot_1/render.mp4", "start_in_output": 0, "duration": 5}])
    result = validate_edl(edl, edit_dir=tmp_path)
    assert not result.ok


def test_escape_windows_drive():
    escaped = escape_subtitles_path(Path(r"C:\Users\Varun B\takes\edit\master.srt"))
    assert escaped.startswith("C\\:")
    assert ":" not in escaped.replace("\\:", "")
    assert "Varun B" in escaped or "Varun\\ B" in escaped
    assert "master.srt" in escaped


def test_default_font_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    assert default_subtitle_font() == "Arial"
    monkeypatch.setattr(sys, "platform", "darwin")
    assert default_subtitle_font() == "Helvetica"


def test_force_style_uses_font():
    style = force_style(font="Arial")
    assert "FontName=Arial" in style
    assert "MarginV=90" in style
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_edl.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'edl'`

- [ ] **Step 3: Implement `helpers/edl.py`**

```python
"""EDL validation and subtitle helpers used by render.py and the local app."""

from __future__ import annotations

import copy
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    edl: dict = field(default_factory=dict)


def _resolve(maybe: str, edit_dir: Path) -> Path:
    p = Path(maybe)
    return p if p.is_absolute() else (edit_dir / p).resolve()


def validate_edl(edl: dict, *, edit_dir: Path) -> ValidationResult:
    out = copy.deepcopy(edl)
    errors: list[str] = []
    warnings: list[str] = []
    sources = out.get("sources")
    ranges = out.get("ranges")
    if not isinstance(sources, dict) or not sources:
        errors.append("sources must be a non-empty object")
        return ValidationResult(False, errors, warnings, out)
    if not isinstance(ranges, list) or not ranges:
        errors.append("ranges must be a non-empty array")
        return ValidationResult(False, errors, warnings, out)

    total = 0.0
    for i, r in enumerate(ranges):
        if not isinstance(r, dict):
            errors.append(f"ranges[{i}] must be an object")
            continue
        name = r.get("source")
        if name not in sources:
            errors.append(f"ranges[{i}].source {name!r} is not in sources")
            continue
        path = _resolve(str(sources[name]), edit_dir)
        if not path.exists():
            errors.append(f"source {name!r} file missing: {path}")
        try:
            start = float(r["start"])
            end = float(r["end"])
        except (KeyError, TypeError, ValueError):
            errors.append(f"ranges[{i}] needs numeric start and end")
            continue
        if start < 0 or end <= start:
            errors.append(f"ranges[{i}] requires 0 <= start < end (got {start}, {end})")
            continue
        total += end - start

    overlays = out.get("overlays") or []
    if overlays:
        if not isinstance(overlays, list):
            errors.append("overlays must be an array")
        else:
            for i, ov in enumerate(overlays):
                if not isinstance(ov, dict) or "file" not in ov:
                    errors.append(f"overlays[{i}] needs a file")
                    continue
                op = _resolve(str(ov["file"]), edit_dir)
                if not op.exists():
                    errors.append(f"overlay file missing: {op}")

    stated = out.get("total_duration_s")
    try:
        stated_f = float(stated) if stated is not None else None
    except (TypeError, ValueError):
        stated_f = None
    if stated_f is None or abs(stated_f - total) > 0.05:
        warnings.append(f"total_duration_s corrected to {total:.3f}")
        out["total_duration_s"] = round(total, 3)

    return ValidationResult(ok=not errors, errors=errors, warnings=warnings, edl=out)


def escape_subtitles_path(path: Path) -> str:
    """Escape a Windows path for ffmpeg subtitles= filter (drive colon + specials)."""
    s = str(path.resolve()).replace("\\", "/")
    s = s.replace("\\", "/")
    s = s.replace(":", r"\:")
    s = s.replace("'", r"\'")
    s = s.replace("[", r"\[")
    s = s.replace("]", r"\]")
    return s


def default_subtitle_font() -> str:
    return "Arial" if sys.platform == "win32" else "Helvetica"


def force_style(*, font: str | None = None, extra: str | None = None) -> str:
    name = font or default_subtitle_font()
    if extra:
        # EDL subtitle_style may be a full force_style or just a font name
        if "FontName=" in extra:
            return extra
        name = extra
    return (
        f"FontName={name},FontSize=18,Bold=1,"
        "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BackColour=&H00000000,"
        "BorderStyle=1,Outline=2,Shadow=0,"
        "Alignment=2,MarginV=90"
    )
```

In `helpers/render.py`:

- After the `configure_stdio()` import in `main()`, leave `main()` as-is except compositing.
- Replace the `SUB_FORCE_STYLE = (...)` constant with:

```python
from edl import force_style, escape_subtitles_path

SUB_FORCE_STYLE = force_style()
```

- In the compositing function, replace the two-line path escape with:

```python
        subs_abs = escape_subtitles_path(subtitles_path)
```

- When building subtitles, if `edl.get("subtitle_style")` is set, use `force_style(extra=str(edl["subtitle_style"]))` instead of `SUB_FORCE_STYLE`. Thread `edl` into `composite()` if it is not already in scope — `main()` has `edl` and already calls the composite helper; add an optional `force_style_str` argument defaulting to `SUB_FORCE_STYLE`.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_edl.py tests/test_stdio.py tests/test_doctor.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add helpers/edl.py helpers/render.py tests/test_edl.py
git commit -m "feat: validate EDL and fix Windows subtitle paths"
```

---

### Task 4: session file + dead-pid reclaim

**Files:**
- Create: `app/__init__.py` (empty)
- Create: `app/server/__init__.py` (empty)
- Create: `app/server/paths.py`
- Create: `app/server/session.py`
- Create: `tests/test_session.py`

**Interfaces:**
- Consumes: nothing
- Produces:

```python
# app/server/paths.py
REPO_ROOT: Path   # parents[2] from this file
HELPERS: Path     # REPO_ROOT / "helpers"
APP_HOME: Path    # Path.home() / ".video-use"

# app/server/session.py
JOB_KINDS = ("idle", "transcribe", "claude", "render")

def default_session(folder: Path) -> dict
def session_path(folder: Path) -> Path   # folder / "edit" / "app_session.json"
def load_session(folder: Path) -> dict
def save_session(folder: Path, data: dict) -> None
def pid_alive(pid: int | None) -> bool
def reclaim_job(data: dict) -> dict
# reclaim: if job.kind != idle and job.pid set and not pid_alive, set
#   data["job"] = {kind: "idle", pid: None, started_at: None, output: None, log: None}
#   data["last_error"] = "previous {old_kind} job died (pid {pid})"
```

`default_session` shape:

```python
{
  "claude_session_id": None,
  "folder": str(folder.resolve()),
  "edl_approved_at": None,
  "edl_mtime_at_approve": 0,
  "last_error": None,
  "job": {"kind": "idle", "pid": None, "started_at": None, "output": None, "log": None},
}
```

- [ ] **Step 1: Write the failing tests**

`tests/test_session.py`:

```python
from __future__ import annotations

from pathlib import Path

from app.server.session import default_session, load_session, pid_alive, reclaim_job, save_session


def test_roundtrip(tmp_path: Path):
    data = default_session(tmp_path)
    save_session(tmp_path, data)
    loaded = load_session(tmp_path)
    assert loaded["folder"] == str(tmp_path.resolve())
    assert loaded["job"]["kind"] == "idle"
    assert (tmp_path / "edit" / "app_session.json").exists()


def test_reclaim_dead_pid():
    data = default_session(Path("C:/footage"))
    data["job"] = {"kind": "render", "pid": 99999999, "started_at": "t", "output": "x", "log": "y"}
    out = reclaim_job(data)
    assert out["job"]["kind"] == "idle"
    assert out["job"]["pid"] is None
    assert "render" in (out.get("last_error") or "")


def test_reclaim_keeps_live_pid():
    import os
    data = default_session(Path("C:/footage"))
    data["job"] = {"kind": "transcribe", "pid": os.getpid(), "started_at": "t", "output": None, "log": None}
    out = reclaim_job(data)
    assert out["job"]["kind"] == "transcribe"
    assert out["job"]["pid"] == os.getpid()


def test_pid_alive_false_for_none():
    assert pid_alive(None) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_session.py -v`

Expected: FAIL with import error for `app.server.session`

- [ ] **Step 3: Implement paths + session**

`app/__init__.py` and `app/server/__init__.py`: empty files.

`app/server/paths.py`:

```python
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HELPERS = REPO_ROOT / "helpers"
APP_HOME = Path.home() / ".video-use"
```

`app/server/session.py`:

```python
from __future__ import annotations

import json
import os
from pathlib import Path

JOB_KINDS = ("idle", "transcribe", "claude", "render")


def default_session(folder: Path) -> dict:
    return {
        "claude_session_id": None,
        "folder": str(folder.resolve()),
        "edl_approved_at": None,
        "edl_mtime_at_approve": 0,
        "last_error": None,
        "job": {"kind": "idle", "pid": None, "started_at": None, "output": None, "log": None},
    }


def session_path(folder: Path) -> Path:
    return folder / "edit" / "app_session.json"


def load_session(folder: Path) -> dict:
    path = session_path(folder)
    if not path.exists():
        return default_session(folder)
    data = json.loads(path.read_text(encoding="utf-8"))
    base = default_session(folder)
    base.update(data)
    if not isinstance(base.get("job"), dict):
        base["job"] = default_session(folder)["job"]
    return reclaim_job(base)


def save_session(folder: Path, data: dict) -> None:
    path = session_path(folder)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def reclaim_job(data: dict) -> dict:
    job = data.get("job") or {}
    kind = job.get("kind") or "idle"
    pid = job.get("pid")
    if kind != "idle" and pid and not pid_alive(int(pid)):
        data["last_error"] = f"previous {kind} job died (pid {pid})"
        data["job"] = {"kind": "idle", "pid": None, "started_at": None, "output": None, "log": None}
    return data
```

On Windows `os.kill(pid, 0)` works for a same-user process check. `PermissionError` means the pid exists; `OSError` / `ProcessLookupError` means it does not.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_session.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/__init__.py app/server/__init__.py app/server/paths.py app/server/session.py tests/test_session.py
git commit -m "feat: persist edit/app_session.json and reclaim dead jobs"
```

---

### Task 5: inventory + recents + helper subprocess env

**Files:**
- Create: `app/server/proc.py`
- Create: `app/server/recents.py`
- Create: `app/server/inventory.py`
- Create: `tests/test_inventory.py`

**Interfaces:**
- Consumes: `HELPERS`, `APP_HOME` from Task 4
- Produces:

```python
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".m4v", ".webm", ".avi"}

def helper_env() -> dict   # os.environ + PYTHONIOENCODING=utf-8 + PYTHONUTF8=1
def find_videos(folder: Path) -> list[Path]
def probe_source(path: Path, *, run=subprocess.run) -> dict
# {name, path, duration_s, width, height, fps, error}
def inventory(folder: Path, *, run=subprocess.run) -> list[dict]
def add_recent(folder: Path) -> list[str]
def load_recents() -> list[str]
```

`probe_source` runs:

`ffprobe -v error -show_entries format=duration -show_entries stream=width,height,avg_frame_rate,codec_type -of json <path>`

Parse the first video stream. On failure set `error` to stderr snippet, numeric fields to `None`.

Recents file: `APP_HOME / "recents.json"` — JSON array of absolute paths, most recent first, max 10, de-duplicated.

- [ ] **Step 1: Write the failing tests**

`tests/test_inventory.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from app.server.inventory import VIDEO_EXTS, find_videos, probe_source
from app.server.proc import helper_env
from app.server.recents import add_recent, load_recents


def test_find_videos_filters(tmp_path: Path):
    (tmp_path / "a.MP4").write_bytes(b"x")
    (tmp_path / "b.webm").write_bytes(b"x")
    (tmp_path / "note.txt").write_bytes(b"x")
    (tmp_path / "edit").mkdir()
    names = {p.name for p in find_videos(tmp_path)}
    assert names == {"a.MP4", "b.webm"}
    assert ".webm" in VIDEO_EXTS


def test_helper_env_forces_utf8(monkeypatch):
    monkeypatch.setenv("FOO", "1")
    env = helper_env()
    assert env["PYTHONIOENCODING"] == "utf-8"
    assert env["PYTHONUTF8"] == "1"
    assert env["FOO"] == "1"


def test_probe_parses_ffprobe():
    payload = {
        "format": {"duration": "12.5"},
        "streams": [
            {"codec_type": "audio"},
            {"codec_type": "video", "width": 1920, "height": 1080, "avg_frame_rate": "30000/1001"},
        ],
    }
    def run(cmd, **kwargs):
        class R:
            returncode = 0
            stdout = json.dumps(payload)
            stderr = ""
        return R()
    info = probe_source(Path("C:/a.mp4"), run=run)
    assert info["duration_s"] == 12.5
    assert info["width"] == 1920
    assert info["height"] == 1080
    assert info["error"] is None


def test_recents_cap_and_dedupe(tmp_path, monkeypatch):
    from app.server import recents as recents_mod
    monkeypatch.setattr(recents_mod, "RECENTS_PATH", tmp_path / "recents.json")
    for i in range(12):
        add_recent(Path(f"C:/f/{i}"))
    add_recent(Path("C:/f/11"))
    items = load_recents()
    assert items[0].endswith("11")
    assert len(items) == 10
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_inventory.py -v`

Expected: FAIL with import error

- [ ] **Step 3: Implement proc, recents, inventory**

`app/server/proc.py`:

```python
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from app.server.paths import HELPERS


def helper_env() -> dict:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def run_helper(script: str, args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess:
    cmd = ["python", str(HELPERS / script), *args]
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=helper_env(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
```

`app/server/recents.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from app.server.paths import APP_HOME

RECENTS_PATH = APP_HOME / "recents.json"
MAX_RECENTS = 10


def load_recents() -> list[str]:
    if not RECENTS_PATH.exists():
        return []
    data = json.loads(RECENTS_PATH.read_text(encoding="utf-8"))
    return [str(p) for p in data] if isinstance(data, list) else []


def add_recent(folder: Path) -> list[str]:
    resolved = str(folder.resolve())
    items = [resolved, *[p for p in load_recents() if p != resolved]]
    items = items[:MAX_RECENTS]
    RECENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RECENTS_PATH.write_text(json.dumps(items, indent=2), encoding="utf-8")
    return items
```

`app/server/inventory.py`:

```python
from __future__ import annotations

import json
import subprocess
from pathlib import Path

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".m4v", ".webm", ".avi"}


def find_videos(folder: Path) -> list[Path]:
    return sorted(
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in VIDEO_EXTS
    )


def _fps(rate: str | None) -> float | None:
    if not rate or rate in ("0/0", "N/A"):
        return None
    if "/" in rate:
        a, b = rate.split("/", 1)
        try:
            return float(a) / float(b)
        except (TypeError, ValueError, ZeroDivisionError):
            return None
    try:
        return float(rate)
    except (TypeError, ValueError):
        return None


def probe_source(path: Path, *, run=subprocess.run) -> dict:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-show_entries", "stream=width,height,avg_frame_rate,codec_type",
        "-of", "json",
        str(path),
    ]
    proc = run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    info = {
        "name": path.name,
        "path": str(path.resolve()),
        "duration_s": None,
        "width": None,
        "height": None,
        "fps": None,
        "error": None,
    }
    if proc.returncode != 0:
        info["error"] = (proc.stderr or "ffprobe failed")[:400]
        return info
    try:
        payload = json.loads(proc.stdout or "{}")
        dur = (payload.get("format") or {}).get("duration")
        info["duration_s"] = float(dur) if dur is not None else None
        for stream in payload.get("streams") or []:
            if stream.get("codec_type") == "video":
                info["width"] = stream.get("width")
                info["height"] = stream.get("height")
                info["fps"] = _fps(stream.get("avg_frame_rate"))
                break
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        info["error"] = str(exc)
    return info


def inventory(folder: Path, *, run=subprocess.run) -> list[dict]:
    return [probe_source(p, run=run) for p in find_videos(folder)]
```

Also add `.webm` / `.WEBM` to `VIDEO_EXTS` in `helpers/transcribe_batch.py` so batch transcribe sees the same files as inventory.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_inventory.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/server/proc.py app/server/recents.py app/server/inventory.py helpers/transcribe_batch.py tests/test_inventory.py
git commit -m "feat: inventory sources and remember recent folders"
```

---

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

### Task 7: FastAPI skeleton — doctor, folder, browse, state

**Files:**
- Create: `app/server/main.py`
- Create: `app/__main__.py`
- Create: `tests/test_api.py`
- Modify: `helpers/transcribe_batch.py` already done for webm

**Interfaces:**
- Consumes: doctor, inventory, recents, session, state
- Produces: FastAPI app `app` in `app/server/main.py`

In-memory (process-global) `CURRENT_FOLDER: Path | None`.

Routes:

- `GET /api/doctor` → `run_doctor().to_dict()`
- `GET /api/recents` → `{ "recents": load_recents() }`
- `POST /api/folder` body `{ "path": "C:\\..." }` → open folder, mkdir `edit/`, `add_recent`, `load_session`, return `project_payload()`
- `POST /api/folder/browse` → tkinter `askdirectory`, then same as folder if not cancelled `{ "cancelled": true }`
- `GET /api/state` → `project_payload()` or 404 if no folder
- `POST /api/open-edit` → `os.startfile(str(folder / "edit"))` on win32

`project_payload()`:

```python
{
  "folder": str,
  "doctor": run_doctor().to_dict(),
  "sources": inventory(folder),
  "recents": load_recents(),
  "center_state": derive_center_state(folder, session),
  "error": session.get("last_error"),
  "packed_markdown": text or null,
  "edl": object or null,
  "has_preview": bool,
  "has_final": bool,
  "chat_enabled": packed exists and doctor.ok,
  "job": session["job"],
  "stale": center_state == "stale",
}
```

CORS allow `http://localhost:5173`.

Do **not** add a transcribe route in this task.

- [ ] **Step 1: Write the failing tests**

`tests/test_api.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.server.main import app, reset_current_folder


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    reset_current_folder()
    from app.server import recents as recents_mod
    monkeypatch.setattr(recents_mod, "RECENTS_PATH", tmp_path / "recents.json")
    return TestClient(app)


def test_doctor(client: TestClient):
    r = client.get("/api/doctor")
    assert r.status_code == 200
    body = r.json()
    assert "ok" in body
    assert "checks" in body
    assert all("sk-" not in c.get("detail", "") for c in body["checks"])


def test_state_without_folder(client: TestClient):
    assert client.get("/api/state").status_code == 404


def test_open_folder_lists_sources(client: TestClient, tmp_path: Path):
    (tmp_path / "take.mp4").write_bytes(b"x")
    r = client.post("/api/folder", json={"path": str(tmp_path)})
    assert r.status_code == 200
    body = r.json()
    assert body["center_state"] in {"inventory", "empty", "error"}
    assert any(s["name"] == "take.mp4" for s in body["sources"])
    assert (tmp_path / "edit").is_dir()
    assert body["chat_enabled"] is False


def test_no_transcribe_route_implied(client: TestClient, tmp_path: Path):
    (tmp_path / "take.mp4").write_bytes(b"x")
    client.post("/api/folder", json={"path": str(tmp_path)})
    # Opening a folder must not create takes_packed.md
    assert not (tmp_path / "edit" / "takes_packed.md").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pip install -e ".[app,dev]"` then `pytest tests/test_api.py -v`

Expected: FAIL with import error for `app.server.main`

- [ ] **Step 3: Implement `app/server/main.py` and `app/__main__.py`**

`app/__main__.py`:

```python
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.server.main:app", host="127.0.0.1", port=8787, reload=True)
```

`app/server/main.py` — implement the routes listed in Interfaces. Include:

```python
from fastapi.middleware.cors import CORSMiddleware

CURRENT_FOLDER: Path | None = None

def reset_current_folder() -> None:
    global CURRENT_FOLDER
    CURRENT_FOLDER = None
```

Browse dialog:

```python
def pick_folder_dialog() -> str | None:
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.wm_attributes("-topmost", 1)
    chosen = filedialog.askdirectory()
    root.destroy()
    return chosen or None
```

`POST /api/folder/browse` is hard to unit test (GUI). Do not test the dialog in pytest; test only `/api/folder`.

For `GET /api/state` 404: `{"detail": "no folder open"}`.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_api.py tests/test_state.py tests/test_session.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/server/main.py app/__main__.py tests/test_api.py
git commit -m "feat: FastAPI doctor and folder endpoints"
```

---

### Task 8: transcribe + pack job

**Files:**
- Create: `app/server/jobs.py`
- Modify: `app/server/main.py`
- Modify: `tests/test_api.py`

**Interfaces:**
- Consumes: `run_helper`, session, `CURRENT_FOLDER`
- Produces:

```python
def start_transcribe(folder: Path) -> dict
# raises RuntimeError if job.kind != idle
# runs in a thread:
#   python helpers/transcribe_batch.py <folder>
#   python helpers/pack_transcripts.py --edit-dir <folder>/edit
# on Scribe 401/quota: last_error = "ElevenLabs rejected the key. Check Developer/video-use/.env"
# never include response body that might contain the key
```

Routes:

- `POST /api/transcribe` → 409 if no folder or job busy; 400 if doctor elevenlabs/ffmpeg not ok; else 202 `{ "accepted": true }`
- Poll via existing `GET /api/state`

Do not start transcribe from `POST /api/folder`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_api.py`:

```python
def test_transcribe_requires_explicit_click(client: TestClient, tmp_path: Path, monkeypatch):
    (tmp_path / "take.mp4").write_bytes(b"x")
    client.post("/api/folder", json={"path": str(tmp_path)})
    called = {"n": 0}
    from app.server import jobs as jobs_mod
    def fake_start(folder):
        called["n"] += 1
        return {"accepted": True}
    monkeypatch.setattr(jobs_mod, "start_transcribe", fake_start)
    # re-import routes use the name bound in main — patch app.server.main.start_transcribe
    import app.server.main as main_mod
    monkeypatch.setattr(main_mod, "start_transcribe", fake_start)
    r = client.post("/api/transcribe")
    assert r.status_code == 202
    assert called["n"] == 1


def test_transcribe_409_when_busy(client: TestClient, tmp_path: Path):
    (tmp_path / "take.mp4").write_bytes(b"x")
    client.post("/api/folder", json={"path": str(tmp_path)})
    from app.server.session import load_session, save_session
    s = load_session(tmp_path)
    s["job"]["kind"] = "transcribe"
    s["job"]["pid"] = 1
    save_session(tmp_path, s)
    r = client.post("/api/transcribe")
    assert r.status_code == 409
```

Add `tests/test_jobs.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from app.server.jobs import start_transcribe
from app.server.session import load_session, save_session, default_session


def test_start_transcribe_rejects_busy(tmp_path: Path):
    (tmp_path / "edit").mkdir()
    s = default_session(tmp_path)
    s["job"]["kind"] = "render"
    s["job"]["pid"] = 1
    save_session(tmp_path, s)
    with pytest.raises(RuntimeError, match="busy"):
        start_transcribe(tmp_path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_api.py tests/test_jobs.py -v`

Expected: FAIL — `start_transcribe` missing and/or `/api/transcribe` 404

- [ ] **Step 3: Implement job runner and route**

`app/server/jobs.py`:

```python
from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path

from app.server.proc import run_helper
from app.server.session import load_session, save_session


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def start_transcribe(folder: Path) -> dict:
    session = load_session(folder)
    if (session.get("job") or {}).get("kind") not in (None, "idle"):
        raise RuntimeError("busy")
    log = folder / "edit" / "transcribe.log"
    session["last_error"] = None
    session["job"] = {"kind": "transcribe", "pid": None, "started_at": _now(), "output": None, "log": str(log)}
    save_session(folder, session)

    def work():
        s = load_session(folder)
        try:
            batch = run_helper("transcribe_batch.py", [str(folder)])
            log.write_text((batch.stdout or "") + (batch.stderr or ""), encoding="utf-8")
            if batch.returncode != 0:
                text = (batch.stderr or batch.stdout or "")
                if "401" in text or "quota" in text.lower() or "returned 401" in text:
                    raise RuntimeError("ElevenLabs rejected the key. Check Developer/video-use/.env")
                raise RuntimeError(text[-400:] or "transcribe failed")
            packed = run_helper("pack_transcripts.py", ["--edit-dir", str(folder / "edit")])
            log.write_text(log.read_text(encoding="utf-8") + (packed.stdout or "") + (packed.stderr or ""), encoding="utf-8")
            if packed.returncode != 0:
                raise RuntimeError((packed.stderr or packed.stdout or "pack failed")[-400:])
            s = load_session(folder)
            s["last_error"] = None
        except Exception as exc:
            s = load_session(folder)
            s["last_error"] = str(exc)
        finally:
            s["job"] = {"kind": "idle", "pid": None, "started_at": None, "output": None, "log": str(log)}
            save_session(folder, s)

    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    # store a sentinel pid so reclaim does not immediately clear; use current pid
    import os
    session = load_session(folder)
    session["job"]["pid"] = os.getpid()
    save_session(folder, session)
    return {"accepted": True}
```

Using the API process pid is intentional: the job lives in a thread of this process. Reclaim on reboot sees this pid dead and marks failed.

Wire `POST /api/transcribe` in `main.py`. Import `start_transcribe` from `app.server.jobs`.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_api.py tests/test_jobs.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/server/jobs.py app/server/main.py tests/test_api.py tests/test_jobs.py
git commit -m "feat: explicit transcribe and pack job"
```

---

### Task 9: Claude adapter

**Files:**
- Create: `app/server/claude.py`
- Create: `tests/test_claude.py`
- Modify: `app/server/main.py`
- Modify: `SKILL.md` (short “driven by the local app” note at the top of The process)

**Interfaces:**
- Consumes: session, `REPO_ROOT`, `HELPERS`
- Produces:

```python
CLAUDE_TIMEOUT_S = 600

EDITOR_BRIEF = """You are the video-use editor for this footage folder.
Read edit/takes_packed.md and edit/project.md if it exists.
Propose or revise a strategy in prose.
Do not write edit/edl.json until you receive a message that begins with STRATEGY_APPROVED.
Do not run ffmpeg, transcribe, render, or install anything.
Write only under edit/.
"""

APPROVE_PROMPT = """STRATEGY_APPROVED
Write edit/edl.json only, using the video-use schema (version, sources, ranges, grade, overlays, subtitles, total_duration_s).
Source paths must be absolute paths to the files in this folder.
Then stop. Do not render.
"""

def claude_cmd(*, folder: Path, session_id: str | None, prompt: str) -> list[str]
def parse_session_id(stream_line: str) -> str | None
def stream_claude(*, folder: Path, prompt: str, session: dict) -> Iterator[str]
# yields text deltas; updates session["claude_session_id"] when seen
# raises RuntimeError on non-zero after the process ends
# timeout CLAUDE_TIMEOUT_S

def ensure_single_claude(session: dict) -> None
# raise RuntimeError("busy") if job.kind == "claude"
```

`claude_cmd` must produce:

First turn (`session_id` is None):

```
claude -p --output-format stream-json --append-system-prompt <EDITOR_BRIEF>
  --allowedTools Read,Write,Edit,Glob,Grep
  --disallowedTools Bash,WebSearch,WebFetch,Agent
  --add-dir <folder> --add-dir <REPO_ROOT>
  <prompt>
```

Later turns: same plus `--resume <session_id>`. Never `--continue`. Never `--dangerously-skip-permissions`.

`parse_session_id`: if the JSON line has `session_id`, return it (covers `type=system` init and `type=result`).

Routes:

- `POST /api/chat` body `{ "message": str }` — 400 if chat disabled; 409 if busy; SSE `text/event-stream` of `{ "text": ... }` chunks, then `{ "done": true }`. Sets `chat_after_approve=True` when the turn finishes (this is not approve).
- `POST /api/chat/retry` — resend `session["last_prompt"]` with the same session id.
- `POST /api/reject` body `{ "note": str }` — stores `session["pending_note"]` and returns 200. Next chat prepends the note.

Do not write `edl.json` in this task from the API.

- [ ] **Step 1: Write the failing tests**

`tests/test_claude.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from app.server.claude import claude_cmd, parse_session_id, EDITOR_BRIEF
from app.server.paths import REPO_ROOT


def test_first_turn_has_no_resume(tmp_path: Path):
    cmd = claude_cmd(folder=tmp_path, session_id=None, prompt="hello")
    assert cmd[0] == "claude"
    assert "-p" in cmd
    assert "--continue" not in cmd
    assert "--resume" not in cmd
    assert "--dangerously-skip-permissions" not in cmd
    assert "--output-format" in cmd
    assert "stream-json" in cmd
    assert "--allowedTools" in cmd
    assert "Bash" in " ".join(cmd)
    # Bash is disallowed
    dis = cmd.index("--disallowedTools")
    assert "Bash" in cmd[dis + 1]
    assert str(tmp_path) in cmd
    assert str(REPO_ROOT) in cmd
    assert any(EDITOR_BRIEF[:20] in a for a in cmd) or "--append-system-prompt" in cmd


def test_later_turn_resumes(tmp_path: Path):
    cmd = claude_cmd(folder=tmp_path, session_id="abc-123", prompt="more")
    assert "--resume" in cmd
    assert "abc-123" in cmd
    assert "--continue" not in cmd


def test_parse_session_id():
    assert parse_session_id('{"type":"system","subtype":"init","session_id":"sid-1"}') == "sid-1"
    assert parse_session_id("not-json") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_claude.py -v`

Expected: FAIL with import error

- [ ] **Step 3: Implement `app/server/claude.py` and chat routes**

Implement `stream_claude` with `subprocess.Popen`, `stdout` line-buffered, `env=helper_env()`, `cwd=folder`. Kill on timeout. Parse stream-json lines: if `type == "assistant"` extract text from `message.content[].text` and yield it; also yield `delta` / `partial` text if present. Persist `claude_session_id` via `save_session` as soon as it appears.

In `SKILL.md`, after the Hard Rules list, add:

```markdown
When you are launched by the video-use local app, do **not** transcribe, render, or call ffmpeg. The app owns those steps. Read `edit/takes_packed.md`, discuss strategy, and write `edit/edl.json` only after `STRATEGY_APPROVED`.
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_claude.py tests/test_api.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/server/claude.py app/server/main.py tests/test_claude.py SKILL.md
git commit -m "feat: stream Claude editorial turns into the app"
```

---

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

### Task 11: Vite UI — layout + state rendering

**Files:**
- Create: `app/web/package.json`, `app/web/vite.config.ts`, `app/web/tsconfig.json`, `app/web/index.html`
- Create: `app/web/src/main.tsx`, `app/web/src/App.tsx`, `app/web/src/api.ts`, `app/web/src/types.ts`, `app/web/src/App.css`
- Create: `app/web/src/centerState.test.ts`
- Create: `app/web/vitest.config.ts`

**Interfaces:**
- Consumes: `GET /api/state` payload from Task 7 (same field names)
- Produces: a three-column page that renders `center_state` and never calls ffmpeg/claude

`app/web/src/api.ts`:

```typescript
export const API = "http://127.0.0.1:8787";

export async function getState() {
  const r = await fetch(`${API}/api/state`);
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}
```

`vite.config.ts` does not need a proxy if `API` is absolute and CORS is on. Keep it simple.

`app/web/src/centerState.test.ts` (vitest):

```typescript
import { describe, it, expect } from "vitest";
import { canChat, canTranscribe, canApprove, canRenderFinal } from "./buttons";

describe("buttons", () => {
  it("empty disables chat and approve", () => {
    expect(canChat("empty", true)).toBe(false);
    expect(canApprove("empty", true)).toBe(false);
    expect(canRenderFinal("preview-ready")).toBe(true);
    expect(canRenderFinal("packed")).toBe(false);
  });
  it("packed enables chat and approve when doctor ok", () => {
    expect(canChat("packed", true)).toBe(true);
    expect(canChat("packed", false)).toBe(false);
    expect(canApprove("packed", true)).toBe(true);
    expect(canApprove("stale", true)).toBe(true);
    expect(canApprove("strategy-ready", true)).toBe(true);
    expect(canApprove("inventory", true)).toBe(false);
  });
});
```

`app/web/src/buttons.ts`:

```typescript
export function canChat(state: string, doctorOk: boolean) {
  return doctorOk && !["empty", "inventory", "transcribing"].includes(state);
}
export function canTranscribe(state: string, doctorOk: boolean) {
  return doctorOk && ["inventory", "packed", "error"].includes(state);
}
export function canApprove(state: string, doctorOk: boolean) {
  return doctorOk && ["packed", "strategy-ready", "stale", "preview-ready", "error"].includes(state);
}
export function canRenderFinal(state: string) {
  return state === "preview-ready";
}
```

- [ ] **Step 1: Scaffold Vite React TS in `app/web`**

Run from repo root:

```powershell
cd app
npm create vite@latest web -- --template react-ts
cd web
npm install
npm install -D vitest
```

If `app/web` already exists, do not re-scaffold; add missing files only.

Set `app/web/vite.config.ts`:

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true },
});
```

Add to `app/web/package.json` scripts: `"test": "vitest run"`.

- [ ] **Step 2: Write the failing button tests, then `buttons.ts`**

Create `app/web/src/buttons.ts` and `app/web/src/centerState.test.ts` with the **correct** rules in Interfaces (not the contradictory draft). Run `npm test` in `app/web` — first without `buttons.ts` to see FAIL, then implement.

- [ ] **Step 3: Build the three-column `App.tsx`**

Left: doctor strip (green/red per check name, never print secrets), path input, Browse (`POST /api/folder/browse` then refresh state), recents list, source list (`name`, `duration_s`, `width`×`height`, `fps`), Open edit (`POST /api/open-edit`).

Center: state label, `error` text, packed transcript `<pre>`, ranges list from `edl.ranges`, `<video src={`${API}/api/media/preview`} controls />` if `has_preview` else first source via `/api/media/source/{name}`, buttons Transcribe / Approve & preview / Render final / Reject (prompt for a note → `POST /api/reject`). Disable from `buttons.ts`. Poll `GET /api/state` every 1s while `job.kind !== "idle"`.

Right: chat log, textarea, Send → `POST /api/chat` (Task 12 if stream not wired yet: show “chat not connected” only if the route 404s; prefer wiring a non-stream JSON fallback). For this task, Send may `POST /api/chat` and then poll state. Streaming is Task 12.

Minimal CSS: three equal columns, full viewport, no framework required.

- [ ] **Step 4: Run UI tests**

Run: `cd app/web; npm test`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/web
git commit -m "feat: three-column local app UI"
```

Do not commit `app/web/node_modules`. Confirm `node_modules/` is gitignored (repo `.gitignore` already has it).

---

### Task 12: chat SSE in the UI + retry

**Files:**
- Modify: `app/web/src/api.ts`
- Modify: `app/web/src/App.tsx`
- Modify: `app/server/main.py` if the chat route is not yet SSE

**Interfaces:**
- Consumes: `POST /api/chat` SSE from Task 9
- Produces: `streamChat(message: string, onText: (t: string) => void): Promise<void>`

```typescript
export async function streamChat(message: string, onText: (t: string) => void) {
  const r = await fetch(`${API}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!r.ok || !r.body) throw new Error(await r.text());
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const parts = buf.split("\n\n");
    buf = parts.pop() || "";
    for (const part of parts) {
      const line = part.replace(/^data:\s*/, "");
      if (!line) continue;
      const ev = JSON.parse(line);
      if (ev.text) onText(ev.text);
    }
  }
}
```

Retry button calls `POST /api/chat/retry` with the same reader loop.

- [ ] **Step 1: Implement `streamChat` + Retry in the right column**

Append assistant text as chunks arrive. On error, show the message and enable Retry.

- [ ] **Step 2: Manual check**

Run API (`python -m app`) and `npm run dev` in `app/web`. Open `http://localhost:5173`. You do not need footage for this step if no folder is open — chat stays disabled. Confirm the page loads and doctor strip appears.

- [ ] **Step 3: Commit**

```bash
git add app/web/src/api.ts app/web/src/App.tsx
git commit -m "feat: stream Claude chat into the review UI"
```

---

### Task 13: installer docs + dev launcher

**Files:**
- Modify: `install.md`
- Create: `app/scripts/dev.ps1`
- Modify: `README.md` (short “Local app (Windows)” paragraph pointing at `install.md` and `app/scripts/dev.ps1`)

**Interfaces:**
- Consumes: ports and extras from the spec
- Produces: one command that starts both processes

- [ ] **Step 1: Write `app/scripts/dev.ps1`**

```powershell
$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $root

Start-Process -NoNewWindow -FilePath "python" -ArgumentList "-m", "uvicorn", "app.server.main:app", "--host", "127.0.0.1", "--port", "8787", "--reload"
Set-Location (Join-Path $root "app\web")
if (-not (Test-Path "node_modules")) { npm install }
npm run dev
```

- [ ] **Step 2: Add a Windows section to `install.md` after the macOS brew block**

```markdown
### Windows

```powershell
# ffmpeg full build (has libass / subtitles)
winget install Gyan.FFmpeg

# Python extras for the local app
cd $HOME\Developer\video-use
pip install -e ".[app,dev]"

# Skill junction (already present on this machine; recreate if needed)
New-Item -ItemType Junction -Path "$HOME\.claude\skills\video-use" -Target "$HOME\Developer\video-use" -Force

# Launch the local app
powershell -File app\scripts\dev.ps1
# UI: http://localhost:5173   API: http://127.0.0.1:8787
```

Do not use `brew`. Do not run Scribe as part of install.
```

- [ ] **Step 3: README paragraph**

Under Manual install, add 4 lines: Windows users can run the local app via `app/scripts/dev.ps1` after `pip install -e ".[app]"`.

- [ ] **Step 4: Commit**

```bash
git add install.md README.md app/scripts/dev.ps1
git commit -m "docs: Windows install and local app launcher"
```

---

### Task 14: manual smoke on this machine

**Files:** none required unless smoke finds a bug (fix + test + commit in the same cycle)

**Interfaces:**
- Consumes: the whole app
- Produces: a working preview/final on real takes, or a filed bug with a failing test

- [ ] **Step 1: Doctor**

Run: `python helpers/doctor.py`

Expected: all checks `ok` on this machine (ffmpeg full build, claude.exe, `.env` present). If libass fails, stop and install `Gyan.FFmpeg` — do not weaken the check.

- [ ] **Step 2: Automated suite**

Run: `pytest tests -v` and `cd app/web; npm test`

Expected: all PASS

- [ ] **Step 3: Launch**

Run: `powershell -File app\scripts\dev.ps1`

Open `http://localhost:5173`. Confirm doctor strip is green.

- [ ] **Step 4: Real folder**

Point the app at a folder with 2–3 talking-head takes. Confirm inventory. Click **Transcribe** (this spends Scribe). Confirm packed transcript appears and chat enables. Do not transcribe from the terminal.

- [ ] **Step 5: Strategy + preview + revision + final**

Chat a short strategy. Click **Approve & preview**. Watch `preview.mp4` in the player. Ask for one change. Approve again. Click **Render final**. Confirm `edit/final.mp4` exists.

If anything fails: write a failing test that reproduces it, fix, commit, re-run from Step 2. Do not declare smoke done with a known broken button.

---

## Self-review (plan vs spec)

| Spec requirement | Task |
|---|---|
| Local website :5173 / API :8787 | 7, 11, 13 |
| Three-column UI, no NLE | 11 |
| Explicit Transcribe only | 8, 11 |
| Claude editorial only, `--resume`, no Bash, no skip-permissions | 9 |
| Approve writes EDL then API renders | 10 |
| Render final API-only | 10 |
| `edit/` source of truth + `app_session.json` + dead pid | 4, 6 |
| Recents in `%USERPROFILE%\.video-use` | 5 |
| UTF-8 helper stdout | 1 |
| doctor.py | 2 |
| EDL validation, Windows subtitle path, Arial font | 3 |
| `.env` never in browser | 2, 7, 11 |
| SKILL.md app-driven note | 9 |
| Windows install.md | 13 |
| Helper/API/UI tests + manual smoke | 1–12, 14 |
| No Grok, no animation UI, no cloud, no push to origin | Global Constraints |

No placeholders left. Types/names are consistent: `run_doctor`, `validate_edl`, `derive_center_state`, `start_transcribe`, `start_approve_and_preview`, `start_render`, `claude_cmd`, `project_payload` fields match the UI.
