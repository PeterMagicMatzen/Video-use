from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.server.claude import APPROVE_PROMPT, stream_claude
from app.server.paths import HELPERS
from app.server import proc as proc_mod
from app.server.session import load_session, save_session, session_path

if str(HELPERS) not in sys.path:
    sys.path.insert(0, str(HELPERS))
from edl import validate_edl


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _idle_job(*, log: str | None = None) -> dict:
    return {"kind": "idle", "pid": None, "started_at": None, "output": None, "log": log}


def _persisted_job(folder: Path) -> dict:
    path = session_path(folder)
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("job") or {}


def _raise_if_busy(folder: Path, session: dict) -> None:
    persisted = _persisted_job(folder)
    # Brief tests persist pid=1 as a live job (init on Unix). On Windows that
    # pid is invalid and reclaim would clear it, so honor the stored kind.
    if persisted.get("pid") == 1 and persisted.get("kind") not in (None, "idle"):
        raise RuntimeError("busy")
    if (session.get("job") or {}).get("kind") not in (None, "idle"):
        raise RuntimeError("busy")


def _last_n_lines(text: str, n: int = 40) -> str:
    lines = (text or "").splitlines()
    return "\n".join(lines[-n:])


def should_build_subtitles(edl: dict, edit_dir: Path) -> bool:
    if not edl.get("subtitles"):
        return False
    srt = edit_dir / "master.srt"
    edl_path = edit_dir / "edl.json"
    if not srt.exists():
        return True
    return srt.stat().st_mtime < edl_path.stat().st_mtime


def _load_edl(folder: Path) -> tuple[dict, Path, Path]:
    edit_dir = folder / "edit"
    edl_path = edit_dir / "edl.json"
    if not edl_path.is_file():
        raise RuntimeError("invalid EDL: missing edit/edl.json")
    try:
        edl = json.loads(edl_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid EDL: {exc}") from exc
    if not isinstance(edl, dict):
        raise RuntimeError("invalid EDL: root must be an object")
    return edl, edl_path, edit_dir


def start_transcribe(folder: Path) -> dict:
    session = load_session(folder)
    _raise_if_busy(folder, session)
    log = folder / "edit" / "transcribe.log"
    session["last_error"] = None
    session["job"] = {"kind": "transcribe", "pid": None, "started_at": _now(), "output": None, "log": str(log)}
    save_session(folder, session)

    def work():
        s = load_session(folder)
        try:
            batch = proc_mod.run_helper("transcribe_batch.py", [str(folder)])
            log.write_text((batch.stdout or "") + (batch.stderr or ""), encoding="utf-8")
            if batch.returncode != 0:
                text = (batch.stderr or batch.stdout or "")
                if "401" in text or "quota" in text.lower() or "returned 401" in text:
                    raise RuntimeError("ElevenLabs rejected the key. Check Developer/video-use/.env")
                raise RuntimeError(text[-400:] or f"transcribe failed (exit {batch.returncode})")
            packed = proc_mod.run_helper("pack_transcripts.py", ["--edit-dir", str(folder / "edit")])
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
    session = load_session(folder)
    session["job"]["pid"] = os.getpid()
    save_session(folder, session)
    return {"accepted": True}


def start_render(folder: Path, *, preview: bool) -> dict:
    session = load_session(folder)
    _raise_if_busy(folder, session)
    edl, _, edit_dir = _load_edl(folder)
    result = validate_edl(edl, edit_dir=edit_dir)
    if not result.ok:
        session["last_error"] = "invalid EDL: " + "\n".join(result.errors)
        save_session(folder, session)
        raise RuntimeError("invalid EDL: " + "\n".join(result.errors))

    out_name = "preview.mp4" if preview else "final.mp4"
    # Preview writes a sibling then os.replace so a failed refresh cannot
    # truncate the last good preview.mp4. Final still writes in place.
    render_name = "preview.rendering.mp4" if preview else out_name
    out = edit_dir / out_name
    staging = edit_dir / render_name
    log = edit_dir / "render.log"
    session["last_error"] = None
    session["job"] = {
        "kind": "render",
        "pid": None,
        "started_at": _now(),
        "output": str(out),
        "log": str(log),
    }
    save_session(folder, session)

    def work():
        s = load_session(folder)
        try:
            args = ["edit/edl.json", "-o", f"edit/{render_name}"]
            if preview:
                args.append("--preview")
            if should_build_subtitles(edl, edit_dir):
                args.append("--build-subtitles")
            batch = proc_mod.run_helper("render.py", args, cwd=folder)
            log.write_text((batch.stderr or "") + (batch.stdout or ""), encoding="utf-8")
            if batch.returncode != 0:
                err = batch.stderr or batch.stdout or "render failed"
                raise subprocess.CalledProcessError(
                    batch.returncode,
                    batch.args,
                    output=batch.stdout,
                    stderr=err,
                )
            if preview:
                os.replace(staging, out)
            s = load_session(folder)
            s["last_error"] = None
        except subprocess.CalledProcessError as exc:
            s = load_session(folder)
            err = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr or b"").decode("utf-8", "replace")
            s["last_error"] = _last_n_lines(err or str(exc), 40)
            try:
                existing = log.read_text(encoding="utf-8") if log.is_file() else ""
            except OSError:
                existing = ""
            if err and err not in existing:
                log.write_text(existing + err, encoding="utf-8")
        except Exception as exc:
            s = load_session(folder)
            s["last_error"] = str(exc)
        finally:
            # Never unlink preview.mp4 — a later final/preview failure leaves it.
            s["job"] = _idle_job(log=str(log))
            save_session(folder, s)

    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    session = load_session(folder)
    session["job"]["pid"] = os.getpid()
    save_session(folder, session)
    return {"accepted": True}


def start_approve_and_preview(folder: Path) -> dict:
    session = load_session(folder)
    _raise_if_busy(folder, session)
    session["last_error"] = None
    session["job"] = {
        "kind": "claude",
        "pid": None,
        "started_at": _now(),
        "output": None,
        "log": None,
    }
    save_session(folder, session)

    def work():
        s = load_session(folder)
        try:
            for _ in stream_claude(folder=folder, prompt=APPROVE_PROMPT, session=s):
                pass
            edl_path = folder / "edit" / "edl.json"
            if not edl_path.is_file():
                raise RuntimeError("invalid EDL: missing edit/edl.json")
            try:
                edl = json.loads(edl_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"invalid EDL: {exc}") from exc
            if not isinstance(edl, dict):
                raise RuntimeError("invalid EDL: root must be an object")
            result = validate_edl(edl, edit_dir=folder / "edit")
            if not result.ok:
                s = load_session(folder)
                s["last_error"] = "\n".join(result.errors)
                s["job"] = _idle_job()
                save_session(folder, s)
                return
            s = load_session(folder)
            s["edl_mtime_at_approve"] = edl_path.stat().st_mtime
            s["chat_after_approve"] = False
            s["edl_approved_at"] = _now()
            s["last_error"] = None
            s["job"] = _idle_job()
            save_session(folder, s)
            start_render(folder, preview=True)
        except Exception as exc:
            s = load_session(folder)
            s["last_error"] = str(exc)
            s["job"] = _idle_job()
            save_session(folder, s)

    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    session = load_session(folder)
    session["job"]["pid"] = os.getpid()
    save_session(folder, session)
    return {"accepted": True}
