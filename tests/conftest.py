from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HELPERS = REPO_ROOT / "helpers"

# Collection-time import of helpers (e.g. `from stdio import ...`) needs path
# before fixtures run.
for _p in (str(REPO_ROOT), str(HELPERS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


@pytest.fixture(autouse=True)
def helpers_on_path():
    for p in (str(REPO_ROOT), str(HELPERS)):
        if p not in sys.path:
            sys.path.insert(0, p)
    yield
