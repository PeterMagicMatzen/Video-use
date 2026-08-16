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
