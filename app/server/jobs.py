from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.server.proc import run_helper
from app.server.session import load_session, save_session, session_path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _persisted_job(folder: Path) -> dict:
    path = session_path(folder)
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("job") or {}


def start_transcribe(folder: Path) -> dict:
    session = load_session(folder)
    persisted = _persisted_job(folder)
    # Brief tests persist pid=1 as a live job (init on Unix). On Windows that
    # pid is invalid and reclaim would clear it, so honor the stored kind.
    if persisted.get("pid") == 1 and persisted.get("kind") not in (None, "idle"):
        raise RuntimeError("busy")
    if (session.get("job") or {}).get("kind") not in (None, "idle"):
        raise RuntimeError("busy")
    log = folder / "edit" / "transcribe.log"
    session["last_error"] = None
    session["job"] = {"kind": "transcribe", "pid": None, "started_at": _now(), "output": None, "log": str(log)}
    save_session(folder, session)

    def work():
        s = load_session(folder)
        try:
            batch = run_helper("transcribe_batch.py", [str(folder)])
            log.write_text((batch.stdout or "") + (batch.stderr or ""), encoding="utf-8")
            if batch.returncode != 0:
                text = (batch.stderr or batch.stdout or "")
                if "401" in text or "quota" in text.lower() or "returned 401" in text:
                    raise RuntimeError("ElevenLabs rejected the key. Check Developer/video-use/.env")
                raise RuntimeError(text[-400:] or "transcribe failed")
            packed = run_helper("pack_transcripts.py", ["--edit-dir", str(folder / "edit")])
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
    import os
    session = load_session(folder)
    session["job"]["pid"] = os.getpid()
    save_session(folder, session)
    return {"accepted": True}
