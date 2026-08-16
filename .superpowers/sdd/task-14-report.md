# Task 14 Report: manual smoke on this machine

## Status

**DONE_WITH_CONCERNS.** Branch `local-app`. Not pushed. No commits. Did not spend ElevenLabs / Scribe credits.

The automated path and the empty-state UI are green. The real Transcribe → chat strategy → Approve & preview → revision → Render final path was **not** run because this machine has no folder of 2–3 short talking-head takes.

## Commits

None.

## What was verified

### Step 1 — Doctor

`python helpers/doctor.py` — all required checks **ok**:

| Check | Detail |
|---|---|
| ffmpeg | `Gyan.FFmpeg` 8.1.1 full build |
| ffprobe | same package |
| claude | `C:\Users\Varun B\.local\bin\claude.EXE` |
| libass | subtitles filter present |
| elevenlabs | present (`.env` key; value not echoed) |

### Step 2 — Automated suite

- `pytest tests -v` — **43 passed**, 1 Starlette/httpx deprecation warning
- `cd app/web; npm.cmd test` — **2 passed** (`centerState.test.ts`)

`npm test` from repo root fails (no root `package.json`). `npm` (`.ps1` shim) is blocked by PowerShell Restricted policy; `npm.cmd` works.

### Step 3 — Launch + doctor strip

`powershell -File app\scripts\dev.ps1` **did not start**: Windows PowerShell execution policy is Restricted (`UnauthorizedAccess` on `dev.ps1`). Per the brief, API + Vite were started directly:

- `python -m uvicorn app.server.main:app --host 127.0.0.1 --port 8787 --reload`
- `npm.cmd run dev` in `app/web` → Vite **http://localhost:5173/**

Opened `http://localhost:5173`. Three-column UI, title `video-use`, state `empty`.

`GET /api/doctor` → `{ "ok": true }` for ffmpeg, ffprobe, claude, libass, elevenlabs.

Playwright computed styles on `.doctor li`: all five have `className=ok` and `color=rgb(0, 170, 0)` (`#0a0`). Strip is green.

Empty-state buttons correctly disabled: Transcribe, Approve & preview, Render final, Reject, Open edit, Chat Send/Retry. Chat placeholder: “Chat disabled until packed”. Recents empty.

`GET /api/state` → 404 (no folder) then client falls back to `/api/doctor` + `/api/recents`. Browser console shows those 404s; expected, not a broken button.

### Footage search (Step 4 prerequisite)

Searched reasonably. **No talking-head take folder.**

| Location | Result |
|---|---|
| `%USERPROFILE%\Videos` | does not exist |
| Desktop | only `urbanrasoi.online` marketing reels |
| `C:\Users\Varun B\Developer` | no `.mp4/.mov/.mkv/.m4v` outside ignored trees |
| Documents | one `meetup1\recap.mp4` (single file, not 2–3 takes) |
| Downloads | no videos |
| Pictures | does not exist |
| OneDrive | no videos |
| Music / Public Videos | none |
| `%USERPROFILE%\.video-use` | does not exist (no recents) |

Desktop `customer-stories` is **not** raw talking-head footage: 6 vertical already-edited Instagram-style reels (branded “CLIENT REVIEW” overlay, grazing-table B-roll). Durations ~36–59s. Per brief, did **not** invent dummy media and did **not** send these to Scribe.

## Remaining smoke (needs the user)

1. Drop a folder of **2–3 short talking-head takes** (or point the app at one that already exists off this machine).
2. Open that folder in the UI (`:5173`) and confirm inventory (names, duration, WxH, fps).
3. Click **Transcribe** (spends Scribe). Confirm packed transcript and that chat enables.
4. Chat a short strategy.
5. **Approve & preview** → watch `preview.mp4` in the player.
6. Ask for one change, approve again.
7. **Render final** → confirm `edit/final.mp4`.

If any of those buttons fail: write a failing test, fix, commit, re-run from doctor/suite. Do not call smoke complete with a known broken control.

## Concerns (not product-button bugs)

1. **No real takes** — full editorial path untested on this machine.
2. **`dev.ps1` blocked by Restricted execution policy.** Documented `powershell -File app\scripts\dev.ps1` fails until the user runs `Set-ExecutionPolicy` or `powershell -ExecutionPolicy Bypass -File app\scripts\dev.ps1`. Smoke used direct uvicorn + Vite instead. Task 13 required that exact command; not changed here.

## Follow-up (docs fix)

Updated `install.md`, `README.md`, and a one-line note in `app/scripts/dev.ps1` so the documented launch is `powershell -ExecutionPolicy Bypass -File app\scripts\dev.ps1` (script process-start behavior unchanged). Commit: `docs: bypass Restricted policy when launching the app`.
3. **`npm` PowerShell shim also blocked**; use `npm.cmd` from `app/web`.

## Self-review

- [x] Doctor all `ok` (did not weaken libass)
- [x] pytest + vitest green
- [x] UI `:5173`, doctor strip green
- [x] Did not transcribe dummy / marketing media
- [x] Stayed on `local-app`; did not push; did not commit `.env`
- [x] No known broken button left unfixed
