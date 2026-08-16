from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.server.inventory import inventory
from app.server.jobs import start_transcribe
from app.server.paths import HELPERS
from app.server.recents import add_recent, load_recents
from app.server.session import load_session
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


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class FolderBody(BaseModel):
    path: str


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
        "has_preview": (folder / "edit" / "preview.mp4").is_file(),
        "has_final": (folder / "edit" / "final.mp4").is_file(),
        "chat_enabled": packed_exists and bool(doctor.get("ok")),
        "job": session["job"],
        "stale": center_state == "stale",
    }


def _open_folder(folder: Path) -> dict:
    global CURRENT_FOLDER
    folder = folder.resolve()
    if not folder.is_dir():
        raise HTTPException(status_code=400, detail="folder not found")
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
