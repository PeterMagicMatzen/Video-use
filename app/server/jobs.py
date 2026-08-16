from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.server.claude import APPROVE_PROMPT, stream_claude
from app.server.paths import HELPERS, REPO_ROOT
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


def spawn_job(kind: str, folder: Path) -> int:
    script = REPO_ROOT / "app" / "scripts" / "run_job.py"
    pid = proc_mod.spawn_detached(
        [sys.executable, str(script), kind, str(folder)],
        cwd=REPO_ROOT,
        log=folder / "edit" / "job.log",
    )
    session = load_session(folder)
    job = session.get("job")
    if isinstance(job, dict):
        job["pid"] = pid
        job["worker_pid"] = pid
        save_session(folder, session)
    return pid


def _has_matching_transcript(folder: Path) -> bool:
    """True only when this folder's .mp4 has its own Scribe JSON."""
    tx = folder / "edit" / "transcripts"
    if not tx.is_dir():
        return False
    video_exts = {".mp4", ".mov", ".mkv", ".m4v", ".webm", ".avi"}
    for video in folder.iterdir():
        if video.is_file() and video.suffix.lower() in video_exts:
            if video.name.endswith("-EDIT.mp4"):
                continue
            if (tx / f"{video.stem}.json").is_file():
                return True
    return False


def _transcribe_body(folder: Path) -> None:
    log = folder / "edit" / "transcribe.log"
    log.parent.mkdir(parents=True, exist_ok=True)
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


def run_transcribe_sync(folder: Path) -> None:
    log = folder / "edit" / "transcribe.log"
    s = load_session(folder)
    try:
        _transcribe_body(folder)
        s = load_session(folder)
        s["last_error"] = None
    except Exception as exc:
        s = load_session(folder)
        s["last_error"] = str(exc)
    finally:
        s["job"] = _idle_job(log=str(log))
        save_session(folder, s)


def run_generate_sync(folder: Path) -> None:
    """Caption-style one shot: captions if needed, then Claude cut + sound, then export."""
    s = load_session(folder)
    s["job"] = {
        "kind": "generate",
        "phase": "transcribe",
        "pid": os.getpid(),
        "worker_pid": os.getpid(),
        "started_at": _now(),
        "output": None,
        "log": str(folder / "edit" / "transcribe.log"),
    }
    s["last_error"] = None
    save_session(folder, s)
    try:
        if not _has_matching_transcript(folder):
            _transcribe_body(folder)
        if not _has_matching_transcript(folder):
            raise RuntimeError("Captions did not finish for this clip. Tap Generate to try again.")
        s = load_session(folder)
        s["job"]["kind"] = "generate"
        s["job"]["phase"] = "directing"
        s["job"]["worker_pid"] = os.getpid()
        s["job"]["pid"] = os.getpid()
        s["job"]["log"] = str(folder / "edit" / "claude_voices.log")
        save_session(folder, s)
        run_auto_edit_sync(folder, claude_audio=True)
    except Exception as exc:
        s = load_session(folder)
        s["last_error"] = str(exc)
        s["job"] = _idle_job()
        save_session(folder, s)
        try:
            (folder / "edit" / "job.log").write_text(f"{exc}\n", encoding="utf-8")
        except OSError:
            pass


def _claude_available() -> bool:
    if str(HELPERS) not in sys.path:
        sys.path.insert(0, str(HELPERS))
    from doctor import run_doctor
    checks = {c["name"]: c for c in run_doctor().to_dict().get("checks") or []}
    return bool(checks.get("claude", {}).get("ok") and checks.get("claude_login", {}).get("ok"))


HISTORY_NAMES = ("edl.json", "voice_picks.json", "cut_picks.json", "claude_score.json")


def snapshot_edit(folder: Path) -> None:
    edit_dir = folder / "edit"
    hist = edit_dir / "history"
    hist.mkdir(parents=True, exist_ok=True)
    for name in HISTORY_NAMES:
        src = edit_dir / name
        if src.is_file():
            shutil.copy2(src, hist / name)


def history_available(folder: Path) -> bool:
    return (folder / "edit" / "history" / "edl.json").is_file()


def restore_history(folder: Path) -> None:
    edit_dir = folder / "edit"
    hist = edit_dir / "history"
    src = hist / "edl.json"
    if not src.is_file():
        raise RuntimeError("nothing to undo")
    for name in HISTORY_NAMES:
        item = hist / name
        dest = edit_dir / name
        if item.is_file():
            shutil.copy2(item, dest)
        elif dest.is_file() and name != "edl.json":
            dest.unlink()


def _load_json_object(path: Path, blob: str) -> object:
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    start = blob.find("{")
    end = blob.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(blob[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None


def _claude_score_cut_and_audio(folder: Path, edl: dict, session: dict, variation: str) -> dict:
    """Claude picks punch-ins/drops and layers Mixkit files."""
    from cut_picks import apply_cut_picks, parse_claude_score, score_prompt, write_cut_brief
    from sfx_library import load_catalog
    from talking_head import apply_claude_titles, load_takes, title_pack
    from voice_picks import apply_voice_picks, catalog_by_id, editorial_catalog, parse_voice_picks, space_audio_picks, write_voice_brief
    from visual_picks import apply_visuals, drop_duplicate_graphics, parse_visuals
    from pexels_library import write_visual_brief
    from graphics import build_talking_head_graphics

    edit_dir = folder / "edit"
    library = editorial_catalog(load_catalog().get("items") or [])
    if not library:
        raise RuntimeError("Mixkit library is empty")
    base_ranges = list(edl.get("ranges") or [])
    write_cut_brief(edit_dir=edit_dir, ranges=base_ranges, variation=variation)
    write_voice_brief(edit_dir=edit_dir, edl=edl, voices=library)
    write_visual_brief(edit_dir)
    chat_sid = session.get("claude_session_id")
    chunks: list[str] = []
    for text in stream_claude(folder=folder, prompt=score_prompt(variation), session=session, resume=False):
        chunks.append(text)
    blob = "".join(chunks)
    (edit_dir / "claude_voices.log").write_text(blob, encoding="utf-8")
    session = load_session(folder)
    if chat_sid:
        session["claude_session_id"] = chat_sid
        save_session(folder, session)
    raw = _load_json_object(edit_dir / "claude_score.json", blob)
    score = parse_claude_score(raw)
    ranges = apply_cut_picks(base_ranges, score["cuts"]) if score["cuts"] else base_ranges
    edl["ranges"] = ranges
    total = round(sum(float(r["end"]) - float(r["start"]) for r in ranges), 3)
    edl["total_duration_s"] = total
    takes = load_takes(edit_dir, folder)
    phrases = [p for t in takes for p in t["phrases"]]
    pack = apply_claude_titles(title_pack(phrases), score.get("titles"))
    edl["overlays"] = build_talking_head_graphics(
        edit_dir=edit_dir,
        speaker=pack.get("name"),
        role=pack.get("role"),
        hook=pack.get("hook") or "",
        keywords=pack.get("keywords") or [],
        end=pack.get("end") or "",
        output_duration=total,
    )
    picks = parse_voice_picks(score, catalog_by_id(library), total_s=total)
    if not picks:
        picks = parse_voice_picks({"picks": score["picks"]}, catalog_by_id(library), total_s=total)
    picks = space_audio_picks(picks, total_s=total)
    user_audio = [a for a in (edl.get("audio_overlays") or []) if a.get("file")]
    if picks:
        apply_voice_picks(edl, picks, replace=True)
        if user_audio:
            apply_voice_picks(edl, user_audio)
    visuals = drop_duplicate_graphics(
        parse_visuals(score),
        hook=str(pack.get("hook") or ""),
        keywords=pack.get("keywords") or [],
    )
    if visuals:
        apply_visuals(edl, visuals, edit_dir, fetch=True)
    (edit_dir / "claude_score.json").write_text(json.dumps({
        "variation": variation,
        "cuts": score["cuts"],
        "picks": [
            {"id": p.get("id"), "start_s": p["start_in_output"], "duration_s": p["duration"], "reason": p.get("reason")}
            for p in picks
        ],
        "visuals": visuals,
        "titles": {
            "hook": pack.get("hook"),
            "name": pack.get("name"),
            "role": pack.get("role"),
            "end": pack.get("end"),
            "keywords": [{"text": k[1], "start_s": k[0]} for k in (pack.get("keywords") or [])],
        },
    }, indent=2), encoding="utf-8")
    if not score["cuts"] and not picks and not visuals:
        raise RuntimeError("Claude did not return cuts, audio, or visuals. Try again.")
    return edl


def run_auto_edit_sync(folder: Path, *, claude_audio: bool = True) -> None:
    try:
        if str(HELPERS) not in sys.path:
            sys.path.insert(0, str(HELPERS))
        from cut_picks import normalize_variation
        from talking_head import build_talking_head_edl
        s = load_session(folder)
        variation = normalize_variation(s.get("cut_variation"))
        use_claude = claude_audio and _claude_available()
        if use_claude:
            s["job"] = {
                "kind": "claude",
                "phase": "directing",
                "pid": os.getpid(),
                "worker_pid": os.getpid(),
                "started_at": _now(),
                "output": None,
                "log": str(folder / "edit" / "claude_voices.log"),
            }
            save_session(folder, s)
        snapshot_edit(folder)
        edl = build_talking_head_edl(folder=folder, edit_dir=folder / "edit", auto_zoom=False)
        if use_claude:
            edl = _claude_score_cut_and_audio(folder, edl, s, variation)
        elif claude_audio:
            raise RuntimeError("Claude is not logged in. Open PowerShell and run: claude auth login")
        edl_path = folder / "edit" / "edl.json"
        edl_path.write_text(json.dumps(edl, indent=2), encoding="utf-8")
        s = load_session(folder)
        s["edl_mtime_at_approve"] = edl_path.stat().st_mtime
        s["chat_after_approve"] = False
        s["edl_approved_at"] = _now()
        s["last_error"] = None
        s["job"] = {
            "kind": "render",
            "phase": "rendering",
            "pid": os.getpid(),
            "worker_pid": os.getpid(),
            "started_at": _now(),
            "output": str(folder / "edit" / "final.mp4"),
            "log": str(folder / "edit" / "render.log"),
        }
        save_session(folder, s)
        _run_render(folder, preview=True)
        _run_render(folder, preview=False)
        _publish_beside_source(folder)
        s = load_session(folder)
        s["last_error"] = None
        s["job"] = _idle_job(log=str(folder / "edit" / "render.log"))
        save_session(folder, s)
    except Exception as exc:
        s = load_session(folder)
        s["last_error"] = str(exc)
        s["job"] = _idle_job()
        save_session(folder, s)


def run_render_sync(folder: Path, *, preview: bool) -> None:
    log = folder / "edit" / "render.log"
    s = load_session(folder)
    try:
        _run_render(folder, preview=preview)
        if not preview:
            _publish_beside_source(folder)
        s = load_session(folder)
        s["last_error"] = None
    except Exception as exc:
        s = load_session(folder)
        s["last_error"] = str(exc)
    finally:
        s["job"] = _idle_job(log=str(log))
        save_session(folder, s)


def start_transcribe(folder: Path) -> dict:
    session = load_session(folder)
    _raise_if_busy(folder, session)
    log = folder / "edit" / "transcribe.log"
    session["last_error"] = None
    session["job"] = {"kind": "transcribe", "pid": None, "started_at": _now(), "output": None, "log": str(log)}
    save_session(folder, session)
    pid = spawn_job("transcribe", folder)
    session = load_session(folder)
    session["job"]["pid"] = pid
    save_session(folder, session)
    return {"accepted": True}


def run_claude_voices_sync(folder: Path) -> None:
    """Same cut as professional edit: Claude cuts + Mixkit bed."""
    run_auto_edit_sync(folder, claude_audio=True)


def run_undo_sync(folder: Path) -> None:
    s = load_session(folder)
    try:
        restore_history(folder)
        s["last_error"] = None
        s["job"] = {
            "kind": "render",
            "pid": os.getpid(),
            "started_at": _now(),
            "output": str(folder / "edit" / "final.mp4"),
            "log": str(folder / "edit" / "render.log"),
        }
        save_session(folder, s)
        _run_render(folder, preview=True)
        _run_render(folder, preview=False)
        _publish_beside_source(folder)
        s = load_session(folder)
        s["last_error"] = None
        s["job"] = _idle_job(log=str(folder / "edit" / "render.log"))
        save_session(folder, s)
    except Exception as exc:
        s = load_session(folder)
        s["last_error"] = str(exc)
        s["job"] = _idle_job()
        save_session(folder, s)


def run_strip_sync(folder: Path) -> None:
    if str(HELPERS) not in sys.path:
        sys.path.insert(0, str(HELPERS))
    from talking_head import build_talking_head_edl
    s = load_session(folder)
    try:
        snapshot_edit(folder)
        edl = build_talking_head_edl(folder=folder, edit_dir=folder / "edit", auto_zoom=False)
        edl_path = folder / "edit" / "edl.json"
        edl_path.write_text(json.dumps(edl, indent=2), encoding="utf-8")
        for name in ("voice_picks.json", "cut_picks.json", "claude_score.json"):
            path = folder / "edit" / name
            if path.is_file():
                path.unlink()
        s["last_error"] = None
        s["job"] = {
            "kind": "render",
            "pid": os.getpid(),
            "started_at": _now(),
            "output": str(folder / "edit" / "final.mp4"),
            "log": str(folder / "edit" / "render.log"),
        }
        save_session(folder, s)
        _run_render(folder, preview=True)
        _run_render(folder, preview=False)
        _publish_beside_source(folder)
        s = load_session(folder)
        s["last_error"] = None
        s["job"] = _idle_job(log=str(folder / "edit" / "render.log"))
        save_session(folder, s)
    except Exception as exc:
        s = load_session(folder)
        s["last_error"] = str(exc)
        s["job"] = _idle_job()
        save_session(folder, s)


def start_undo(folder: Path) -> dict:
    session = load_session(folder)
    _raise_if_busy(folder, session)
    if not history_available(folder):
        raise RuntimeError("nothing to undo")
    session["last_error"] = None
    session["job"] = {
        "kind": "render",
        "pid": None,
        "started_at": _now(),
        "output": None,
        "log": str(folder / "edit" / "render.log"),
    }
    save_session(folder, session)
    pid = spawn_job("undo", folder)
    session = load_session(folder)
    session["job"]["pid"] = pid
    save_session(folder, session)
    return {"accepted": True}


def start_strip(folder: Path) -> dict:
    session = load_session(folder)
    _raise_if_busy(folder, session)
    session["last_error"] = None
    session["job"] = {
        "kind": "render",
        "pid": None,
        "started_at": _now(),
        "output": None,
        "log": str(folder / "edit" / "render.log"),
    }
    save_session(folder, session)
    pid = spawn_job("strip", folder)
    session = load_session(folder)
    session["job"]["pid"] = pid
    save_session(folder, session)
    return {"accepted": True}


def start_claude_voices(folder: Path, variation: str | None = None) -> dict:
    if str(HELPERS) not in sys.path:
        sys.path.insert(0, str(HELPERS))
    from cut_picks import normalize_variation
    session = load_session(folder)
    _raise_if_busy(folder, session)
    session["cut_variation"] = normalize_variation(variation)
    session["last_error"] = None
    session["job"] = {
        "kind": "claude",
        "pid": None,
        "started_at": _now(),
        "output": None,
        "log": str(folder / "edit" / "claude_voices.log"),
    }
    save_session(folder, session)
    pid = spawn_job("generate", folder)
    session = load_session(folder)
    session["job"]["pid"] = pid
    save_session(folder, session)
    return {"accepted": True}


def start_auto_edit(folder: Path, variation: str | None = None) -> dict:
    """Claude cinematic cuts + Mixkit sound bed."""
    if str(HELPERS) not in sys.path:
        sys.path.insert(0, str(HELPERS))
    from cut_picks import normalize_variation
    session = load_session(folder)
    _raise_if_busy(folder, session)
    session["cut_variation"] = normalize_variation(variation)
    session["last_error"] = None
    session["job"] = {
        "kind": "claude",
        "pid": None,
        "started_at": _now(),
        "output": None,
        "log": str(folder / "edit" / "claude_voices.log"),
    }
    save_session(folder, session)
    pid = spawn_job("generate", folder)
    session = load_session(folder)
    session["job"]["pid"] = pid
    save_session(folder, session)
    return {"accepted": True}


def _publish_beside_source(folder: Path) -> Path | None:
    src = folder / "edit" / "final.mp4"
    if not src.is_file():
        src = folder / "edit" / "preview.mp4"
    if not src.is_file():
        return None
    videos = [
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in {".mp4", ".mov", ".mkv", ".m4v", ".webm", ".avi"}
        and not p.name.endswith("-EDIT.mp4")
        and p.name not in {"preview.mp4", "final.mp4"}
    ]
    if not videos:
        dest = folder / "final-EDIT.mp4"
    else:
        dest = folder / f"{videos[0].stem}-EDIT.mp4"
    shutil.copy2(src, dest)
    return dest


def _run_render(folder: Path, *, preview: bool) -> None:
    edl, _, edit_dir = _load_edl(folder)
    result = validate_edl(edl, edit_dir=edit_dir)
    if not result.ok:
        raise RuntimeError("invalid EDL: " + "\n".join(result.errors))
    out_name = "preview.mp4" if preview else "final.mp4"
    render_name = "preview.rendering.mp4" if preview else out_name
    out = edit_dir / out_name
    staging = edit_dir / render_name
    log = edit_dir / "render.log"
    args = ["edit/edl.json", "-o", f"edit/{render_name}"]
    if preview:
        args.append("--preview")
    if should_build_subtitles(edl, edit_dir):
        args.append("--build-subtitles")
    batch = proc_mod.run_helper("render.py", args, cwd=folder)
    prev = log.read_text(encoding="utf-8") if log.is_file() else ""
    log.write_text(prev + (batch.stderr or "") + (batch.stdout or ""), encoding="utf-8")
    if batch.returncode != 0:
        err = batch.stderr or batch.stdout or "render failed"
        raise RuntimeError(_last_n_lines(err, 40))
    if preview:
        os.replace(staging, out)


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
    pid = spawn_job("render-preview" if preview else "render-final", folder)
    session = load_session(folder)
    session["job"]["pid"] = pid
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
