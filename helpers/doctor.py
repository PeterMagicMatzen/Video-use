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
