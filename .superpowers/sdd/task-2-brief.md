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

