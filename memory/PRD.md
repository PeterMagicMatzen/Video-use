# ClipCut — Cinematic Reel Editor (Cloud Web App)

## Original Problem Statement
"so i am building this video edit tool... the core goal is just 1. it should function like caption ai video editor."

Follow-up (June 2026): "Add a cinematic reel-editor. The core feature is a speech-driven auto-editor:
after upload the AI must transcribe the audio and use the speech patterns to trigger automatic cuts
and smooth digital zooms. Use Cloudinary's transformation API to handle the video processing and
smooth zooming effects. The UI should be a simple 'Upload and Generate' flow that shows the final
edited preview." Plus: Karaoke Highlight (exported captions light up word-by-word in yellow),
Vertical Reframe (landscape → 9:16, speaker auto-centered), Project Library (past uploads in the left rail).

User choices:
- Cloud web app, single-video flow, NO login for v1
- ElevenLabs Scribe for transcription (key in /app/backend/.env)
- Heuristic cuts (no Claude CLI)
- Cloudinary API key + secret supplied; CLOUDINARY_CLOUD_NAME still MISSING

## Architecture
- Backend: FastAPI (/app/backend/server.py) on :8001, all routes /api prefixed
  - transcription.py — ElevenLabs Scribe (scribe_v1, word timestamps)
  - cuts.py — heuristic spans: pauses > threshold + filler words → keep_ranges
  - zooms.py — speech-driven camera plan (push in / pull out / punch / hold) from
    words-per-second energy + emphatic punctuation; zoom amp 1.045–1.17x
  - reframe.py — OpenCV haar face detection (opencv-python-headless 4.11) → median
    normalised x of the speaker for 9:16 crop centering
  - render_engine.py — per-segment ffmpeg: HDR tonemap → 9:16 crop @ speaker centre →
    1.3x prescale + zoompan smooth digital zoom → concat → ASS karaoke burn → loudnorm -14 LUFS.
    Returns meta {width,height,aspect,moves,center_x,caption_events,karaoke}
  - cloudinary_svc.py — signed backend upload of the finished reel + `ar_9:16,c_fill,g_auto`
    transformation URL for CDN delivery. Gated on all 3 env vars being present (currently OFF).
- Frontend: React 18 + craco + Tailwind (/app/frontend)
  - screens/ReelStudio.jsx — DEFAULT VIEW: one-click Upload & Generate (upload → transcribe →
    render), staged progress, result panel with stats + camera-plan chips + preview + download
  - screens/Editor.jsx — 3-pane fine-tune editor (rail / stage / transcript)
  - components/ProjectLibrary.jsx — library list w/ thumbnails, reopen, delete (both views)
- MongoDB `projects` collection (uuid string ids). Files on disk at /app/backend/data/{project_id}/

## API Endpoints (/api)
- POST /projects/upload/init, /projects/{id}/upload/chunk, /projects/{id}/upload/complete
- GET  /projects  (library list)         DELETE /projects/{id}
- GET  /projects/{id}                    GET /projects/{id}/thumbnail (lazy-generated)
- POST /projects/{id}/cuts               POST /projects/{id}/style
- POST /projects/{id}/reel  {aspect, cinematic, karaoke, zoom_intensity, burn_captions}
- GET  /projects/{id}/video              GET /projects/{id}/export/video (range 206)
- POST /projects/{id}/export {caption_style, burn_captions, aspect, cinematic, karaoke, zoom_intensity}
- GET  /projects/{id}/export/download    GET /cloudinary/status    GET /styles

## Implemented
### 2026-06 (session 1)
- Chunked upload → Scribe transcription → auto-cuts → live caption preview → styled export → download
- 4 caption styles mirrored between preview CSS and burned output; faststart remux; range streaming

### 2026-06 (session 2 — cinematic reel editor)
- Speech-driven camera plan (zooms.py) + smooth zoompan digital zooms per speech beat
- Word-by-word KARAOKE highlight in the exported captions (ASS inline `\c&H00FFD4&` yellow + 108% pop)
- Vertical Reframe: 9:16 crop with OpenCV face-centered x (verified center_x 0.27 on off-centre landscape)
- Project Library in both rails: thumbnails, duration, reel badge, reopen, delete
- One-click "Upload & Generate" studio as the app entry, staged progress, in-app reel preview,
  camera-plan chips, download / fine-tune / re-generate
- Cloudinary layer written and wired (signed upload + `ar_9:16,c_fill,g_auto` delivery URL) but
  INACTIVE until CLOUDINARY_CLOUD_NAME is set; local FFmpeg path handles everything meanwhile
- Tested: testing agent iteration_2 — backend 10/10, frontend 100% of testable flows, 0 issues

### 2026-06 (session 3 — keyword punch-ins + Cloudinary creds)
- zooms.py: emphasis scoring per word (pace-relative elongation vs the speaker's own median
  sec/char, terminal !/?, held-then-beat gaps, hook lexicon, digits, long words). Words scoring
  ≥0.85 get a hard zoom SNAP: instant +7–14% zoom, linear decay over 0.38s, max 5 per segment,
  min 1.4s apart, capped so total zoom stays under the 1.3x prescale (stays sharp)
- render_engine: composite zoompan expression = linear base move + `if(between(on,f0,f1),...)`
  snap terms. Verified objectively: face height 805px → 885px (+10%) at the punch, decaying back
- meta now returns `punches` (word + timestamp) and `punch_count`; UI shows a Punch-ins stat and
  "Punched words" chips; `punch_ins` toggle in both the studio recipe and the editor rail
- CLOUDINARY_CLOUD_NAME set to `clipcut` but Cloudinary rejects it ("Invalid cloud_name") — the
  upload is wrapped so exports still succeed and the error surfaces in the UI (`cloud-error`)

## Backlog
- P0: correct CLOUDINARY_CLOUD_NAME from the user → cloud reframe + CDN preview delivery
- P1: editable transcript text before export (fix Scribe mistranscriptions)
- P1: draggable/resizable caption box in the preview that maps 1:1 to the export
- P2: beat-synced b-roll / punch-in on keyword hits
- P2: caption position + font-size controls
- P2: disk cleanup job for old project folders

## Notes / Gotchas
- OpenCV 5.x REMOVED cv2.CascadeClassifier — pinned opencv-python-headless==4.11.0.86
- Only Liberation fonts exist in the container (no DejaVu) → ASS Fontname = "Liberation Sans"
- ASS WrapStyle 0 (smart wrap) — WrapStyle 2 caused caption overflow past the margins
- zoompan needs zoom >= 1; we prescale 1.3x before zoompan so zooms stay sharp
- ElevenLabs key is FREE tier: STT works, TTS blocked (payment_required)
- Headless Chromium in preview cannot decode H.264 → <video> renders black in screenshots
