from __future__ import annotations

import json
import queue
import subprocess
import threading
import time
from collections.abc import Iterator
from pathlib import Path

from app.server.paths import REPO_ROOT
from app.server.proc import helper_env
from app.server.session import save_session

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
Set "grade" to "none" unless the user explicitly asked for a look. Do not use warm_cinematic.
Then stop. Do not render.
"""


def claude_cmd(*, folder: Path, session_id: str | None, prompt: str) -> list[str]:
    cmd = [
        "claude",
        "-p",
        "--output-format",
        "stream-json",
        "--permission-mode",
        "acceptEdits",
        "--append-system-prompt",
        EDITOR_BRIEF,
        "--allowedTools",
        "Read,Write,Edit,Glob,Grep",
        "--disallowedTools",
        "Bash,WebSearch,WebFetch,Agent",
        "--add-dir",
        str(folder),
        "--add-dir",
        str(REPO_ROOT),
    ]
    if session_id:
        cmd.extend(["--resume", session_id])
    cmd.append(prompt)
    return cmd


def parse_session_id(stream_line: str) -> str | None:
    try:
        data = json.loads(stream_line)
    except json.JSONDecodeError:
        return None
    sid = data.get("session_id")
    if isinstance(sid, str) and sid:
        return sid
    return None


def ensure_single_claude(session: dict) -> None:
    if (session.get("job") or {}).get("kind") == "claude":
        raise RuntimeError("busy")


def _text_from_value(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    if isinstance(value, dict):
        text = value.get("text")
        if isinstance(text, str) and text:
            return text
    return None


def _assistant_texts(data: dict) -> list[str]:
    if data.get("type") != "assistant":
        return []
    message = data.get("message") or {}
    content = message.get("content") or []
    texts: list[str] = []
    if isinstance(content, str) and content:
        texts.append(content)
        return texts
    if not isinstance(content, list):
        return texts
    for block in content:
        text = _text_from_value(block)
        if text:
            texts.append(text)
    return texts


def _delta_or_partial_text(data: dict) -> list[str]:
    out: list[str] = []
    for key in ("delta", "partial"):
        text = _text_from_value(data.get(key))
        if text:
            out.append(text)
    return out


def stream_claude(*, folder: Path, prompt: str, session: dict) -> Iterator[str]:
    cmd = claude_cmd(
        folder=folder,
        session_id=session.get("claude_session_id"),
        prompt=prompt,
    )
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(folder),
        env=helper_env(),
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    job = session.get("job")
    if isinstance(job, dict):
        job["pid"] = proc.pid
        save_session(folder, session)

    lines: queue.Queue[str | None] = queue.Queue()
    stderr_chunks: list[str] = []

    def _read_stdout() -> None:
        try:
            if proc.stdout is not None:
                for line in proc.stdout:
                    lines.put(line)
        finally:
            lines.put(None)

    def _read_stderr() -> None:
        if proc.stderr is not None:
            stderr_chunks.append(proc.stderr.read() or "")

    threading.Thread(target=_read_stdout, daemon=True).start()
    threading.Thread(target=_read_stderr, daemon=True).start()

    timed_out = False
    deadline = time.monotonic() + CLAUDE_TIMEOUT_S
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            try:
                line = lines.get(timeout=min(1.0, remaining))
            except queue.Empty:
                continue
            if line is None:
                break
            sid = parse_session_id(line)
            if sid:
                session["claude_session_id"] = sid
                save_session(folder, session)
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict):
                continue
            for text in _assistant_texts(data):
                yield text
            for text in _delta_or_partial_text(data):
                yield text
            event = data.get("event")
            if isinstance(event, dict):
                for text in _delta_or_partial_text(event):
                    yield text
        if timed_out:
            if proc.poll() is None:
                proc.kill()
            raise RuntimeError("claude timeout")
        returncode = proc.wait(timeout=max(1.0, deadline - time.monotonic()))
        if returncode != 0:
            err = "".join(stderr_chunks).strip()
            raise RuntimeError(err[-400:] or f"claude exited {returncode}")
    finally:
        if proc.poll() is None:
            proc.kill()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
