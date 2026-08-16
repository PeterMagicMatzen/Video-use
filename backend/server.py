import os
import re
import shutil
import subprocess
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")

from fastapi import FastAPI, APIRouter, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pymongo import MongoClient

import cuts as cuts_mod
import render_engine
import transcription

client = MongoClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]
projects = db.projects

DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Captions Editor API")
api = APIRouter(prefix="/api")

DEFAULT_CUT_SETTINGS = {"pause_threshold": 0.8, "remove_fillers": True, "disabled": []}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def project_dir(pid: str) -> Path:
    return DATA_DIR / pid


def get_project_or_404(pid: str) -> dict:
    doc = projects.find_one({"id": pid}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "project not found")
    return doc


def compute_cut_state(doc: dict) -> dict:
    settings = doc.get("cut_settings") or DEFAULT_CUT_SETTINGS
    words = doc.get("words") or []
    duration = doc.get("duration") or 0
    spans = cuts_mod.compute_spans(words, duration, settings["pause_threshold"], settings["remove_fillers"])
    disabled = set(settings.get("disabled") or [])
    ranges = cuts_mod.keep_ranges(duration, spans, disabled)
    for s in spans:
        s["disabled"] = s["id"] in disabled
    kept = sum(b - a for a, b in ranges)
    return {
        "spans": spans,
        "keep_ranges": ranges,
        "kept_duration": round(kept, 2),
        "removed_duration": round(max(0, duration - kept), 2),
        "settings": settings,
    }


# ---------- Upload (chunked) ----------

class InitUpload(BaseModel):
    filename: str
    size: int


@api.post("/projects/upload/init")
def init_upload(body: InitUpload):
    if not re.search(r"\.(mp4|mov|m4v|webm|mkv|avi)$", body.filename, re.I):
        raise HTTPException(400, "unsupported file type")
    pid = str(uuid.uuid4())
    pdir = project_dir(pid)
    (pdir / "chunks").mkdir(parents=True)
    doc = {
        "id": pid,
        "filename": body.filename,
        "size": body.size,
        "status": "uploading",
        "error": None,
        "duration": 0,
        "width": 0,
        "height": 0,
        "words": [],
        "text": "",
        "cut_settings": dict(DEFAULT_CUT_SETTINGS),
        "caption_style": "bold",
        "export": {"status": "idle", "progress": 0, "error": None},
        "created_at": now_iso(),
    }
    projects.insert_one(doc)
    return {"project_id": pid}


@api.post("/projects/{pid}/upload/chunk")
def upload_chunk(pid: str, index: int = Form(...), chunk: UploadFile = File(...)):
    get_project_or_404(pid)
    dest = project_dir(pid) / "chunks" / f"{index:06d}.part"
    with open(dest, "wb") as f:
        shutil.copyfileobj(chunk.file, f)
    return {"ok": True, "index": index}


@api.post("/projects/{pid}/upload/complete")
def complete_upload(pid: str):
    doc = get_project_or_404(pid)
    pdir = project_dir(pid)
    chunks_dir = pdir / "chunks"
    parts = sorted(chunks_dir.glob("*.part"))
    if not parts:
        raise HTTPException(400, "no chunks uploaded")
    ext = Path(doc["filename"]).suffix.lower() or ".mp4"
    raw_path = pdir / f"raw{ext}"
    with open(raw_path, "wb") as out:
        for p in parts:
            with open(p, "rb") as f:
                shutil.copyfileobj(f, out)
    shutil.rmtree(chunks_dir, ignore_errors=True)

    video_path = pdir / f"source{ext}"
    remux = subprocess.run(
        ["ffmpeg", "-y", "-i", str(raw_path), "-c", "copy", "-movflags", "+faststart", str(video_path)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if remux.returncode == 0:
        raw_path.unlink(missing_ok=True)
    else:
        raw_path.replace(video_path)

    try:
        info = render_engine.probe(video_path)
    except Exception:
        shutil.rmtree(pdir, ignore_errors=True)
        projects.delete_one({"id": pid})
        raise HTTPException(400, "file is not a valid video")

    projects.update_one({"id": pid}, {"$set": {
        "status": "transcribing",
        "video_path": str(video_path),
        "duration": info["duration"],
        "width": info["width"],
        "height": info["height"],
    }})
    threading.Thread(target=_run_transcription, args=(pid,), daemon=True).start()
    return {"ok": True, "status": "transcribing", "duration": info["duration"]}


def _run_transcription(pid: str):
    doc = projects.find_one({"id": pid})
    try:
        payload = transcription.transcribe_video(Path(doc["video_path"]))
        words = payload.get("words") or []
        projects.update_one({"id": pid}, {"$set": {
            "status": "ready",
            "words": words,
            "text": payload.get("text") or "",
        }})
    except Exception as e:
        projects.update_one({"id": pid}, {"$set": {"status": "error", "error": str(e)[:500]}})


# ---------- Project state ----------

@api.get("/projects/{pid}")
def get_project(pid: str):
    doc = get_project_or_404(pid)
    doc.pop("video_path", None)
    if doc["status"] == "ready":
        doc["cuts"] = compute_cut_state(doc)
    return doc


class CutSettings(BaseModel):
    pause_threshold: float = 0.8
    remove_fillers: bool = True
    disabled: list[str] = []


@api.post("/projects/{pid}/cuts")
def update_cuts(pid: str, body: CutSettings):
    doc = get_project_or_404(pid)
    if doc["status"] != "ready":
        raise HTTPException(400, "transcript not ready")
    settings = {
        "pause_threshold": max(0.3, min(3.0, body.pause_threshold)),
        "remove_fillers": body.remove_fillers,
        "disabled": body.disabled,
    }
    projects.update_one({"id": pid}, {"$set": {"cut_settings": settings}})
    doc["cut_settings"] = settings
    return compute_cut_state(doc)


class StyleBody(BaseModel):
    caption_style: str


@api.post("/projects/{pid}/style")
def set_style(pid: str, body: StyleBody):
    get_project_or_404(pid)
    if body.caption_style not in render_engine.CAPTION_STYLES:
        raise HTTPException(400, "unknown style")
    projects.update_one({"id": pid}, {"$set": {"caption_style": body.caption_style}})
    return {"ok": True}


# ---------- Video streaming ----------

@api.get("/projects/{pid}/video")
def stream_video(pid: str, request: Request):
    doc = projects.find_one({"id": pid})
    if not doc or not doc.get("video_path"):
        raise HTTPException(404, "video not found")
    path = Path(doc["video_path"])
    if not path.exists():
        raise HTTPException(404, "video not found")
    file_size = path.stat().st_size
    range_header = request.headers.get("range")

    def iter_file(start: int, end: int, chunk_size: int = 1024 * 1024):
        with open(path, "rb") as f:
            f.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                data = f.read(min(chunk_size, remaining))
                if not data:
                    break
                remaining -= len(data)
                yield data

    headers = {"Accept-Ranges": "bytes", "Content-Type": "video/mp4"}
    m = re.match(r"bytes=(\d+)-(\d*)", range_header) if range_header else None
    if m:
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else file_size - 1
        end = min(end, file_size - 1)
        headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        headers["Content-Length"] = str(end - start + 1)
        return StreamingResponse(iter_file(start, end), status_code=206, headers=headers)
    headers["Content-Length"] = str(file_size)
    return StreamingResponse(iter_file(0, file_size - 1), headers=headers)


# ---------- Export ----------

class ExportBody(BaseModel):
    caption_style: str = "bold"
    burn_captions: bool = True


@api.post("/projects/{pid}/export")
def start_export(pid: str, body: ExportBody):
    doc = get_project_or_404(pid)
    if doc["status"] != "ready":
        raise HTTPException(400, "transcript not ready")
    if (doc.get("export") or {}).get("status") == "processing":
        raise HTTPException(400, "export already running")
    projects.update_one({"id": pid}, {"$set": {
        "caption_style": body.caption_style,
        "export": {"status": "processing", "progress": 0, "error": None},
    }})
    threading.Thread(target=_run_export, args=(pid, body.caption_style, body.burn_captions), daemon=True).start()
    return {"ok": True}


def _run_export(pid: str, style_key: str, burn: bool):
    doc = projects.find_one({"id": pid})
    try:
        state = compute_cut_state(doc)
        pdir = project_dir(pid)
        out_path = pdir / "export.mp4"

        def cb(p):
            projects.update_one({"id": pid}, {"$set": {"export.progress": p}})

        render_engine.render_export(
            source=Path(doc["video_path"]),
            words=doc.get("words") or [],
            ranges=state["keep_ranges"],
            style_key=style_key,
            burn=burn,
            work_dir=pdir / "work",
            out_path=out_path,
            progress_cb=cb,
        )
        projects.update_one({"id": pid}, {"$set": {
            "export": {"status": "done", "progress": 100, "error": None, "path": str(out_path)},
        }})
        shutil.rmtree(pdir / "work", ignore_errors=True)
    except Exception as e:
        projects.update_one({"id": pid}, {"$set": {
            "export": {"status": "error", "progress": 0, "error": str(e)[:500]},
        }})


@api.get("/projects/{pid}/export/download")
def download_export(pid: str):
    doc = get_project_or_404(pid)
    export = doc.get("export") or {}
    if export.get("status") != "done":
        raise HTTPException(404, "export not ready")
    path = Path(export["path"])
    if not path.exists():
        raise HTTPException(404, "export file missing")
    stem = Path(doc["filename"]).stem
    return FileResponse(path, media_type="video/mp4", filename=f"{stem}_edited.mp4")


@api.get("/styles")
def list_styles():
    return {"styles": list(render_engine.CAPTION_STYLES.keys())}


@api.get("/")
def health():
    return {"status": "ok"}


app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
