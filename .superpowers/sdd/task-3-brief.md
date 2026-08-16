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

