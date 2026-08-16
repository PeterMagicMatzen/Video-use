# ClipCut — Captions-AI-Style Video Editor (Cloud Web App)

## Original Problem Statement
"so i am building this video edit tool. can you see what's working and what can be bettered. the core goal is just 1. it should function like caption ai video editor."

User choices (confirmed via ask_human in prior session):
- Rebuild the legacy local desktop tool as a cloud web app
- Single-video upload flow, NO login/auth for v1
- ElevenLabs Scribe for transcription (user provided API key, stored in /app/backend/.env)
- Heuristic cuts only — NO Claude/AI cuts
- Captions + cuts + export = core feature set

## Architecture
- Backend: FastAPI (/app/backend/server.py) on :8001, all routes prefixed /api
  - transcription.py — ElevenLabs Scribe (scribe_v1, word timestamps) via ffmpeg audio extract
  - cuts.py — heuristic spans: pauses > threshold (0.3–3.0s) + filler words (um/uh/hmm...), merge, keep-ranges
  - render_engine.py — ffmpeg export: per-range extract (HDR tonemap, portrait-aware scale, 30ms audio fades) → concat → SRT build (3-word chunks) → burn ASS-styled captions → loudnorm -14 LUFS
- Frontend: React 18 + CRA/craco + Tailwind (/app/frontend), 3-pane editor per /app/design_guidelines.json ("Performance Pro" dark + Cyber Yellow #D4FF00)
- MongoDB `projects` collection (uuid string ids, no ObjectId). Video files on disk at /app/backend/data/{project_id}/
- Legacy desktop code remains at /app/app/ and /app/helpers/ (reference only, not used at runtime)

## API Endpoints (all /api prefix)
- POST /projects/upload/init {filename,size} → {project_id}
- POST /projects/{id}/upload/chunk (form: index, chunk) — 5MB chunks from frontend
- POST /projects/{id}/upload/complete — assemble, faststart remux, probe, spawn transcription thread
- GET  /projects/{id} — full state incl. computed `cuts` when ready
- POST /projects/{id}/cuts {pause_threshold, remove_fillers, disabled[]}
- POST /projects/{id}/style {caption_style}
- GET  /projects/{id}/video — range-streaming
- POST /projects/{id}/export {caption_style, burn_captions} → background render, progress in doc
- GET  /projects/{id}/export/download

## Caption Styles
bold / neon (cyber yellow) / boxed / minimal — mirrored in backend ASS force_style (render_engine.CAPTION_STYLES) and frontend CSS (src/lib/captions.js CAPTION_STYLES).

## Implemented (2026-06, this session)
- Full backend + frontend built from scratch, e2e tested (testing agent iteration_1: backend 100%, frontend 95% — video decode limitation is headless-Chromium-only, not an app bug)
- Chunked upload → Scribe transcription → auto-cuts → live caption preview → styled export → download: ALL WORKING
- Hardening: video onError fallback, malformed Range fallback, upload poll timeout, faststart remux on upload
- Test video with speech at /app/memory/testvid.mp4 (14.7s, contains 2.5s silence gap)

## Backlog
- P1: Editable transcript text (correct Scribe mistranscriptions before export)
- P1: Word-by-word karaoke highlight in exported captions (ASS \k tags) — preview already highlights active word
- P2: Multiple caption positions / font size control
- P2: Project persistence UI (list past projects; backend already stores them)
- P2: 9:16 auto-reframe for landscape sources
- P2: Cleanup job for old project files on disk

## Notes / Gotchas
- ElevenLabs key is FREE tier: TTS API blocked (payment_required), Scribe STT works
- Headless Chromium in preview env can't decode H.264 — testing agents must remove CRA error-overlay iframes; real browsers fine
- espeak-ng installed for generating test speech videos
