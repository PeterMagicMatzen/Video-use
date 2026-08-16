### Task 14: manual smoke on this machine

**Files:** none required unless smoke finds a bug (fix + test + commit in the same cycle)

**Interfaces:**
- Consumes: the whole app
- Produces: a working preview/final on real takes, or a filed bug with a failing test

- [ ] **Step 1: Doctor**

Run: `python helpers/doctor.py`

Expected: all checks `ok` on this machine (ffmpeg full build, claude.exe, `.env` present). If libass fails, stop and install `Gyan.FFmpeg` — do not weaken the check.

- [ ] **Step 2: Automated suite**

Run: `pytest tests -v` and `cd app/web; npm test`

Expected: all PASS

- [ ] **Step 3: Launch**

Run: `powershell -File app\scripts\dev.ps1`

Open `http://localhost:5173`. Confirm doctor strip is green.

- [ ] **Step 4: Real folder**

Point the app at a folder with 2–3 talking-head takes. Confirm inventory. Click **Transcribe** (this spends Scribe). Confirm packed transcript appears and chat enables. Do not transcribe from the terminal.

- [ ] **Step 5: Strategy + preview + revision + final**

Chat a short strategy. Click **Approve & preview**. Watch `preview.mp4` in the player. Ask for one change. Approve again. Click **Render final**. Confirm `edit/final.mp4` exists.

If anything fails: write a failing test that reproduces it, fix, commit, re-run from Step 2. Do not declare smoke done with a known broken button.

---

## Self-review (plan vs spec)

| Spec requirement | Task |
|---|---|
| Local website :5173 / API :8787 | 7, 11, 13 |
| Three-column UI, no NLE | 11 |
| Explicit Transcribe only | 8, 11 |
| Claude editorial only, `--resume`, no Bash, no skip-permissions | 9 |
| Approve writes EDL then API renders | 10 |
| Render final API-only | 10 |
| `edit/` source of truth + `app_session.json` + dead pid | 4, 6 |
| Recents in `%USERPROFILE%\.video-use` | 5 |
| UTF-8 helper stdout | 1 |
| doctor.py | 2 |
| EDL validation, Windows subtitle path, Arial font | 3 |
| `.env` never in browser | 2, 7, 11 |
| SKILL.md app-driven note | 9 |
| Windows install.md | 13 |
| Helper/API/UI tests + manual smoke | 1–12, 14 |
| No Grok, no animation UI, no cloud, no push to origin | Global Constraints |

No placeholders left. Types/names are consistent: `run_doctor`, `validate_edl`, `derive_center_state`, `start_transcribe`, `start_approve_and_preview`, `start_render`, `claude_cmd`, `project_payload` fields match the UI.
