from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from app.server.claude import ensure_single_claude, stream_claude
from app.server.inventory import VIDEO_EXTS, find_videos, inventory
from app.server.jobs import start_approve_and_preview, start_auto_edit, start_render, start_transcribe
from app.server.paths import HELPERS
from app.server.recents import add_recent, load_recents
from app.server.session import load_session, save_session, session_path
from app.server.state import derive_center_state

if str(HELPERS) not in sys.path:
    sys.path.insert(0, str(HELPERS))
from doctor import run_doctor

CURRENT_FOLDER: Path | None = None


def reset_current_folder() -> None:
    global CURRENT_FOLDER
    CURRENT_FOLDER = None


def pick_folder_dialog() -> str | None:
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.wm_attributes("-topmost", 1)
    chosen = filedialog.askdirectory()
    root.destroy()
    return chosen or None


def pick_video_dialog() -> str | None:
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.wm_attributes("-topmost", 1)
    chosen = filedialog.askopenfilename(
        title="Choose a video",
        filetypes=[
            ("Video", "*.mp4 *.mov *.mkv *.m4v *.webm *.avi"),
            ("All files", "*.*"),
        ],
    )
    root.destroy()
    return chosen or None


def resolve_footage_path(raw: str) -> Path:
    """Folder, or a video file (use its parent folder)."""
    text = raw.strip().strip('"').strip("'")
    path = Path(text).expanduser()
    if path.is_file() and path.suffix.lower() in VIDEO_EXTS:
        return path.parent
    return path


def restore_last_folder() -> None:
    recents = load_recents()
    if not recents:
        return
    path = Path(recents[0])
    if path.is_dir():
        try:
            _open_folder(path)
        except HTTPException:
            return


app = FastAPI(on_startup=[restore_last_folder])
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class FolderBody(BaseModel):
    path: str


class ChatBody(BaseModel):
    message: str


class RejectBody(BaseModel):
    note: str


def project_payload(folder: Path | None = None) -> dict:
    folder = folder if folder is not None else CURRENT_FOLDER
    if folder is None:
        raise HTTPException(status_code=404, detail="no folder open")
    session = load_session(folder)
    doctor = run_doctor().to_dict()
    packed_path = folder / "edit" / "takes_packed.md"
    edl_path = folder / "edit" / "edl.json"
    packed_exists = packed_path.is_file()
    packed_markdown = packed_path.read_text(encoding="utf-8") if packed_exists else None
    preview_path = folder / "edit" / "preview.mp4"
    has_preview = preview_path.is_file()
    preview_mtime = preview_path.stat().st_mtime if has_preview else None
    edl = None
    if edl_path.is_file():
        try:
            edl = json.loads(edl_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            edl = None
    center_state = derive_center_state(folder, session)
    return {
        "folder": str(folder.resolve()),
        "doctor": doctor,
        "sources": inventory(folder),
        "recents": load_recents(),
        "center_state": center_state,
        "error": session.get("last_error"),
        "packed_markdown": packed_markdown,
        "edl": edl,
        "has_preview": has_preview,
        "preview_mtime": preview_mtime,
        "has_final": (folder / "edit" / "final.mp4").is_file(),
        "chat_enabled": packed_exists and any(
            c.get("name") == "claude_login" and c.get("ok") for c in doctor.get("checks", [])
        ),
        "auto_edit_enabled": packed_exists,
        "job": session["job"],
        "stale": center_state == "stale",
    }


def _open_folder(folder: Path) -> dict:
    global CURRENT_FOLDER
    folder = resolve_footage_path(str(folder)).resolve()
    if not folder.is_dir():
        raise HTTPException(
            status_code=400,
            detail="Not a footage folder. Open the folder that contains the .mp4, or pick the file itself.",
        )
    (folder / "edit").mkdir(exist_ok=True)
    add_recent(folder)
    load_session(folder)
    CURRENT_FOLDER = folder
    return project_payload(folder)


@app.get("/api/doctor")
def get_doctor() -> dict:
    return run_doctor().to_dict()


@app.get("/api/recents")
def get_recents() -> dict:
    return {"recents": load_recents()}


@app.post("/api/folder")
def post_folder(body: FolderBody) -> dict:
    return _open_folder(Path(body.path))


@app.post("/api/folder/browse")
def post_folder_browse() -> dict:
    chosen = pick_folder_dialog()
    if not chosen:
        return {"cancelled": True}
    return _open_folder(Path(chosen))


@app.post("/api/folder/browse-file")
def post_folder_browse_file() -> dict:
    chosen = pick_video_dialog()
    if not chosen:
        return {"cancelled": True}
    return _open_folder(Path(chosen))


@app.get("/api/state")
def get_state() -> dict:
    return project_payload()


@app.post("/api/open-edit")
def post_open_edit() -> dict:
    if CURRENT_FOLDER is None:
        raise HTTPException(status_code=404, detail="no folder open")
    edit = CURRENT_FOLDER / "edit"
    edit.mkdir(exist_ok=True)
    if sys.platform == "win32":
        os.startfile(str(edit))
    return {"ok": True}


@app.post("/api/transcribe", status_code=202)
def post_transcribe() -> dict:
    if CURRENT_FOLDER is None:
        raise HTTPException(status_code=409, detail="no folder open")
    doctor = run_doctor().to_dict()
    checks = {c["name"]: c for c in doctor["checks"]}
    if not checks.get("elevenlabs", {}).get("ok") or not checks.get("ffmpeg", {}).get("ok"):
        raise HTTPException(status_code=400, detail="doctor elevenlabs/ffmpeg not ok")
    try:
        return start_transcribe(CURRENT_FOLDER)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _idle_job() -> dict:
    return {"kind": "idle", "pid": None, "started_at": None, "output": None, "log": None}


def _persisted_job(folder: Path) -> dict:
    path = session_path(folder)
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("job") or {}


def _require_open_folder() -> Path:
    if CURRENT_FOLDER is None:
        raise HTTPException(status_code=404, detail="no folder open")
    return CURRENT_FOLDER


def _chat_enabled(folder: Path) -> bool:
    packed = (folder / "edit" / "takes_packed.md").is_file()
    doctor = run_doctor().to_dict()
    return packed and bool(doctor.get("ok"))


def _require_chat_ready(folder: Path) -> dict:
    if not _chat_enabled(folder):
        raise HTTPException(status_code=400, detail="chat disabled")
    session = load_session(folder)
    persisted = _persisted_job(folder)
    if persisted.get("pid") == 1 and persisted.get("kind") not in (None, "idle"):
        raise HTTPException(status_code=409, detail="busy")
    try:
        ensure_single_claude(session)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if (session.get("job") or {}).get("kind") not in (None, "idle"):
        raise HTTPException(status_code=409, detail="busy")
    return session


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def _begin_claude_job(folder: Path, session: dict, prompt: str) -> dict:
    session["last_prompt"] = prompt
    session["last_error"] = None
    session["job"] = {
        "kind": "claude",
        "pid": os.getpid(),
        "started_at": _now(),
        "output": None,
        "log": None,
    }
    save_session(folder, session)
    return session


def _stream_chat_turn(folder: Path, session: dict, prompt: str):
    _begin_claude_job(folder, session, prompt)

    def events():
        try:
            for chunk in stream_claude(folder=folder, prompt=prompt, session=session):
                yield _sse({"text": chunk})
            session["chat_after_approve"] = True
            session["last_error"] = None
        except Exception as exc:
            session["last_error"] = str(exc)
            yield _sse({"error": str(exc)})
        finally:
            session["job"] = _idle_job()
            save_session(folder, session)
        yield _sse({"done": True})

    return StreamingResponse(events(), media_type="text/event-stream")


@app.post("/api/chat")
def post_chat(body: ChatBody):
    folder = _require_open_folder()
    session = _require_chat_ready(folder)
    note = session.pop("pending_note", None)
    prompt = f"{note}\n\n{body.message}" if note else body.message
    return _stream_chat_turn(folder, session, prompt)


@app.post("/api/chat/retry")
def post_chat_retry():
    folder = _require_open_folder()
    session = _require_chat_ready(folder)
    last = session.get("last_prompt")
    if not last:
        raise HTTPException(status_code=400, detail="no prompt to retry")
    return _stream_chat_turn(folder, session, last)


@app.post("/api/reject")
def post_reject(body: RejectBody) -> dict:
    folder = _require_open_folder()
    session = load_session(folder)
    session["pending_note"] = body.note
    save_session(folder, session)
    return {"ok": True}


def _job_http_error(exc: RuntimeError) -> HTTPException:
    msg = str(exc)
    code = 409 if "busy" in msg.lower() else 400
    return HTTPException(status_code=code, detail=msg)


@app.post("/api/auto-edit", status_code=202)
def post_auto_edit() -> dict:
    if CURRENT_FOLDER is None:
        raise HTTPException(status_code=409, detail="no folder open")
    packed = CURRENT_FOLDER / "edit" / "takes_packed.md"
    if not packed.is_file():
        raise HTTPException(status_code=400, detail="transcribe first")
    try:
        return start_auto_edit(CURRENT_FOLDER)
    except RuntimeError as exc:
        raise _job_http_error(exc) from exc


@app.post("/api/approve", status_code=202)
def post_approve() -> dict:
    if CURRENT_FOLDER is None:
        raise HTTPException(status_code=409, detail="no folder open")
    try:
        return start_approve_and_preview(CURRENT_FOLDER)
    except RuntimeError as exc:
        raise _job_http_error(exc) from exc


@app.post("/api/render-final", status_code=202)
def post_render_final() -> dict:
    if CURRENT_FOLDER is None:
        raise HTTPException(status_code=409, detail="no folder open")
    try:
        return start_render(CURRENT_FOLDER, preview=False)
    except RuntimeError as exc:
        raise _job_http_error(exc) from exc


@app.get("/api/media/preview")
def get_media_preview():
    folder = _require_open_folder()
    path = folder / "edit" / "preview.mp4"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="preview not found")
    return FileResponse(path, media_type="video/mp4")


@app.get("/api/media/final")
def get_media_final():
    folder = _require_open_folder()
    path = folder / "edit" / "final.mp4"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="final not found")
    return FileResponse(path, media_type="video/mp4")


@app.get("/api/media/source/{name}")
def get_media_source(name: str):
    folder = _require_open_folder()
    if not name or name in {".", ".."} or "/" in name or "\\" in name:
        raise HTTPException(status_code=404, detail="source not found")
    match = next((p for p in find_videos(folder) if p.name == name), None)
    if match is None or not match.is_file():
        raise HTTPException(status_code=404, detail="source not found")
    return FileResponse(match)
