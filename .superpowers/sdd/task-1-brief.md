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

