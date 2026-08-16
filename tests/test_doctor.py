from __future__ import annotations

from pathlib import Path

from doctor import run_doctor


def _which_ok(name: str):
    return f"C:/tools/{name}.exe"


def _which_missing(name: str):
    return None


def _run_ok(cmd, **_k):
    class R:
        returncode = 0
        stdout = " T. subtitles     A V  Subtitle filter\n"

    if cmd and len(cmd) >= 2 and cmd[1] == "auth":
        R.stdout = '{"loggedIn": true, "authMethod": "oauth"}'
    return R()


def _run_filters(cmd=None, **_k):
    return _run_ok(cmd or ["ffmpeg", "-filters"], **_k)


def test_all_required_ok():
    report = run_doctor(which=_which_ok, run=_run_filters, key_loader=lambda: "sk-test")
    assert report.ok
    assert {c.name for c in report.checks} == {
        "ffmpeg", "ffprobe", "libass", "claude", "claude_login", "elevenlabs",
    }
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


def test_claude_login_required():
    def run(cmd, **_k):
        class R:
            returncode = 0
            stdout = " T. subtitles     A V  Subtitle filter\n"
        if cmd and len(cmd) >= 2 and cmd[1] == "auth":
            R.stdout = '{"loggedIn": false, "authMethod": "none"}'
        return R()
    report = run_doctor(which=_which_ok, run=run, key_loader=lambda: "x")
    login = next(c for c in report.checks if c.name == "claude_login")
    assert login.ok is False
    assert "claude auth login" in login.detail


def test_libass_absent():
    def run(cmd, **_k):
        class R:
            stdout = '{"loggedIn": true}'
            returncode = 0
        if cmd and cmd[0] and "ffmpeg" in str(cmd[0]):
            R.stdout = " T. scale         V  Scale\n"
        return R()
    report = run_doctor(which=_which_ok, run=run, key_loader=lambda: "x")
    libass = next(c for c in report.checks if c.name == "libass")
    assert libass.ok is False
    assert libass.required is True
