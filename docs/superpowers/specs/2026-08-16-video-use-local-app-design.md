# video-use local app

Date: 2026-08-16  
Status: draft, awaiting user review  
Repo: `C:\Users\Varun B\Developer\video-use` (existing clone; Claude skill is a junction to this path)

A local website on this Windows machine that turns the video-use skill + helpers into a talking-head editor: drop takes, chat a strategy, review transcript and ranges, preview, then render `final.mp4`.

## Problem

video-use is a strong editing pipeline, but it is not a product. It is `SKILL.md` plus six Python helpers that an agent must orchestrate. On this machine that is painful:

- There is no window to pick a folder, see the packed transcript, or play a preview.
- Helpers crash on Windows when they print `→` to a non-UTF-8 stdout (upstream #125).
- Install docs assume `brew`. There is no doctor command (upstream #121).
- Subtitle burn-in hardcodes Helvetica and has fragile path escaping (upstream #118, #124).
- The editorial brain (Claude Code) and the mechanical steps (Scribe, ffmpeg) share one chat, so a render failure looks like a conversation failure.

## Goals

On this machine, with 2–3 talking-head takes in a folder:

1. Open a local page, pick the folder, see doctor status and source durations.
2. Transcribe and pack without Claude touching Scribe.
3. Chat a strategy with Claude Code, then approve it in the UI.
4. Watch `edit/preview.mp4`, ask for one change, approve again, render `edit/final.mp4`.
5. Do that without using a terminal after the app is started.

## Non-goals (v1)

- Timeline dragging, ripple edit, clip inspector
- Animation-slot UI, color-wheel grading, music / B-roll library
- Multi-folder tabs, accounts, cloud, billing
- Grok as the editor brain
- Auto-starting transcription (Scribe costs money)
- Contributing the app to `browser-use/video-use` (helper fixes may become later PRs)
- `--dangerously-skip-permissions` on Claude

## Users

One user: the owner of this Windows machine. One footage folder at a time.

## Decisions already locked

| Decision | Choice |
|---|---|
| Product shape | Local website, not a desktop shell |
| Audience | Single user, this machine |
| Job | Talking-head / multi-take |
| UI | Chat + review panel, not chat-only and not a full NLE |
| Editor brain | Claude Code CLI already installed (`claude.exe`) |
| Mechanical steps | Python API owns doctor, inventory, transcribe, pack, render |
| Repo | Same tree as the skill and helpers |
| Transcribe trigger | Explicit **Transcribe** click, never implicit |
| Folder picker | Absolute path field + server-side Browse dialog |
| Ports | UI `localhost:5173`, API `localhost:8787` |

## Architecture

Three processes, one footage folder:

```
[Vite/React :5173]  <--HTTP/SSE-->  [FastAPI :8787]  --spawns-->  [claude.exe -p]
                                         |
                                         +-- imports / subprocesses helpers/
                                         +-- reads/writes <folder>/edit/
```

- **Web UI** never calls ffmpeg or Claude. It talks only to the API.
- **Control plane** is the only process that runs helpers or starts `claude.exe`.
- **Claude Code** is editorial only: read `edit/takes_packed.md`, discuss strategy, write `edit/edl.json`. It does not transcribe or render.

`~/.claude/skills/video-use` is already a junction to this repo. Helpers have a single source of truth.

Work happens on a local git branch (`local-app`). Do not push this product to `origin` (`browser-use/video-use`).

### Layout

```
video-use/
  helpers/                 # existing scripts, Windows-hardened
  SKILL.md                 # Claude skill (brief updated: no transcribe/render)
  app/
    server/                # FastAPI control plane
    web/                   # Vite + React + TypeScript
  docs/superpowers/specs/  # this document
```

Python app extras (`fastapi`, `uvicorn`, `pydantic`) live in an optional `[app]` extra in `pyproject.toml`. The UI is a separate npm project under `app/web/`.

A single launcher (`python -m app` or `app/scripts/dev.ps1`) starts API + Vite for development. Production v1 may serve the built UI from FastAPI; not required for the first smoke.

## UI

One page, three columns, no router maze.

### Left — sources

- Doctor strip: ffmpeg, `claude.exe`, ElevenLabs key (present / missing / rejected). Never display the key.
- Folder field + Browse. Recent folders from `%USERPROFILE%\.video-use\recents.json`.
- Source list from `ffprobe` (name, duration, resolution, fps).
- Actions: change folder, open `edit/` in Explorer.
- No account UI. No settings beyond folder + doctor.

### Center — review

- Packed transcript from `edit/takes_packed.md` (phrase list, selectable for chat context).
- Proposed ranges from `edit/edl.json`: beat, quote, start–end, source take. A list, not a timeline.
- Player: `edit/preview.mp4` if present, else the selected source clip.
- Buttons: **Approve & preview**, **Render final**, **Reject / send note to chat**.

Center states:

| State | Meaning |
|---|---|
| empty | No folder, or folder with no videos |
| inventory | Folder picked, sources listed, not transcribed |
| transcribing | Scribe job running |
| packed | `takes_packed.md` exists, no current EDL |
| strategy-ready | Current `edl.json` written since last approve, not yet rendered |
| rendering | ffmpeg job running |
| preview-ready | `preview.mp4` matches the current approved EDL |
| stale | Chat happened after the EDL on disk; approve required before preview refresh |
| error | Last job failed; previous preview stays playable if it exists |

### Right — chat

Streaming tokens from `claude -p`. Strategy is prose in this column. Approve is a center button, not a chat command. Chat is disabled until `takes_packed.md` exists.

### v1 does not include

Drag-to-trim, animation slot UI, color-wheel grading, multi-project tabs, cloud upload.

## Data flow

1. Pick folder. API creates `edit/` if missing, runs doctor, probes every video (`mp4`, `mov`, `mkv`, `m4v`, `webm`, `avi`), returns the source list, appends the path to recents.
2. User clicks **Transcribe**. API runs `helpers/transcribe_batch.py` then `helpers/pack_transcripts.py`. Cached Scribe JSON is reused. Chat stays disabled until pack succeeds.
3. First chat turn: API starts `claude -p` in the footage folder and stores the session id in `edit/app_session.json`. Later turns use `--continue` / resume of that id.
4. Every Claude invocation prepends a fixed brief:
   - You are the video-use editor for this folder.
   - Read `edit/takes_packed.md` (and `edit/project.md` if present).
   - Propose or revise a strategy in prose.
   - Do not write `edl.json` until the API says the strategy is approved.
   - Do not run ffmpeg, transcribe, render, or install anything.
   - Write only under `edit/`.
5. **Approve & preview**:
   1. API sends Claude a structured turn: “strategy approved — write `edit/edl.json` only, then stop.”
   2. API validates the file (see Contracts).
   3. API runs `helpers/render.py edit/edl.json -o edit/preview.mp4 --preview`.
6. Later chat may make the EDL stale. Render never starts from a chat turn. Approve is the only render trigger for preview.
7. **Render final**: API runs `helpers/render.py edit/edl.json -o edit/final.mp4`. Claude is not invoked.

Reject / send note copies the note into the next chat turn. It does not delete files.

## Contracts

### `edit/edl.json`

Keep the existing video-use schema:

```json
{
  "version": 1,
  "sources": {"C0103": "C:/abs/path/C0103.MP4"},
  "ranges": [
    {
      "source": "C0103",
      "start": 2.42,
      "end": 6.85,
      "beat": "HOOK",
      "quote": "...",
      "reason": "..."
    }
  ],
  "grade": "none",
  "overlays": [],
  "subtitles": "edit/master.srt",
  "total_duration_s": 87.4
}
```

API validation before any ffmpeg call:

- `sources` keys match `ranges[].source`
- each source path exists
- `start < end` and both ≥ 0
- `total_duration_s` is present and equals the sum of range lengths within 0.05s (warn + auto-correct if off, do not fail)
- if `overlays` is non-empty, each `file` exists (v1 has no animation UI; missing overlay files fail validation)
- unknown extra keys are ignored

Invalid EDL: do not call ffmpeg; center state is `error` with the schema message; chat stays open.

v1 render flags: preview uses `--preview`. Final does not. If the EDL has a `subtitles` field, pass `--build-subtitles` unless the file already exists and is newer than the EDL. Grade is whatever string is in the EDL (`none`, a preset name, `auto`, or a raw filter). No grade UI.

### `edit/app_session.json`

```json
{
  "claude_session_id": "<id or null>",
  "folder": "C:/abs/footage",
  "edl_approved_at": "2026-08-16T12:00:00+00:00",
  "edl_mtime_at_approve": 0,
  "job": {
    "kind": "idle",
    "pid": null,
    "started_at": null,
    "output": null,
    "log": null
  }
}
```

`kind` is `idle` | `transcribe` | `claude` | `render`. On API boot: if `pid` is set and dead, mark the job failed and leave artifacts; if alive, reconnect to the log file. No orphan-killer beyond that.

`stale` means `edl.json` mtime is newer than `edl_mtime_at_approve` but no preview has been rendered from it, or chat completed after `edl_approved_at` without a new approve.

### Claude invocation

- Binary: `C:\Users\Varun B\.local\bin\claude.exe` (resolved via `PATH` / doctor).
- `cwd`: the footage folder.
- `--add-dir` for the footage folder and this repo (so the skill and helpers are readable).
- Allowed tools: Read, Write, Edit, Glob, Grep. Denied: Bash and all web/network tools. Claude must not be able to start a shell.
- No `--dangerously-skip-permissions`.
- First turn: `claude -p --output-format stream-json`. Persist the session id from that run into `edit/app_session.json`.
- Later turns: always `claude -p --resume <id> --output-format stream-json`. Do not use `--continue` — that can attach to a different conversation the user started in the same folder.
- One Claude process per folder at a time. Retry resends the same prompt into the same session. Never start a second Claude against the same folder.

### Helpers

Imported / invoked from `helpers/` in this repo. Not copied into `app/`. Every helper subprocess gets `PYTHONIOENCODING=utf-8` and `PYTHONUTF8=1`.

## Windows hardening (helpers)

These land in the same helpers the API calls:

1. Reconfigure stdout to UTF-8 (`errors=replace`) at each helper entry point so `→` / `—` / `…` cannot raise `UnicodeEncodeError`.
2. `helpers/doctor.py` (new): check `ffmpeg`, `ffprobe`, `subtitles` filter (libass), `claude.exe`, and `ELEVENLABS_API_KEY` (present, not echoed). Exit non-zero if a hard requirement is missing.
3. Subtitle path escaping that survives Windows drive letters (`C:\...`) in the ffmpeg `subtitles=` filter.
4. Default force-style font is Arial on Windows, Helvetica elsewhere, overridable later via an EDL `subtitle_style` key (optional in v1; if absent, use the OS default above).

`install.md` gets a Windows section: WinGet ffmpeg full build, `pip install -e .[app]`, junction already exists, do not use `brew`.

## Error handling

Hard stop (disable the relevant button, show a fix, do not retry blindly):

- Doctor fail → transcribe / chat / render disabled; strip names the missing binary or key.
- Scribe 401 / quota → transcribe fails; UI says “ElevenLabs rejected the key”; point at `Developer/video-use/.env`; never print the secret.
- Invalid EDL → no ffmpeg.
- Render `CalledProcessError` → last ffmpeg stderr lines in the error panel; previous preview stays playable.

Recoverable:

- Claude non-zero or hang (timeout 10 minutes per turn) → chat error + **Retry turn**. Session id kept.
- App restart mid-job → `app_session.json` pid check as above.
- Stale EDL → Approve required to refresh preview.

Safety:

- `.env` never sent to the browser. UI only sees `present` | `missing` | `rejected`.
- Claude cannot start transcribe/render jobs. Only the API can.

## Testing

Automated:

- Helper tests: UTF-8 print on a cp1252 stdout, doctor checks with fakes, EDL validator, Windows subtitle path escaping.
- API tests: fake Claude subprocess; generated silent mp4 for inventory; fixture Scribe JSON → pack; valid/invalid EDL; render dry-run (or ffmpeg-available extract of 0.5s).
- UI tests: center-state mapping for empty, packed, strategy-ready, error. No Playwright suite in v1.

Not in CI: live Claude, live Scribe.

Manual smoke (success definition): doctor green, transcribe one short take, approve a strategy, preview plays, one chat revision, `final.mp4` exists.

## Operations

- Secrets stay in `Developer/video-use/.env` (already gitignored).
- Recents and any app log live under `%USERPROFILE%\.video-use\`, not inside the repo.
- Footage `edit/` stays next to the sources, never inside the repo.

## Implementation order (for the later plan, not work now)

1. Helper hardening + doctor + EDL validator + tests
2. FastAPI: folder pick, inventory, transcribe/pack jobs, session file
3. Claude adapter: start/resume/stream, brief, approve-write-EDL
4. Render jobs + preview/final paths
5. Vite UI: three columns, states, player
6. Manual smoke on this machine

## Open items explicitly closed

- No second product name. This is the video-use local app.
- No Grok fallback in v1.
- No auto-transcribe.
- Overlays may appear in an EDL if Claude writes them and the files exist; there is no UI to create them.
- Source-faithful fps/resolution (upstream #64) is not v1. Preview/final use current `render.py` behavior.
