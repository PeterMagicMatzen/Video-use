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
