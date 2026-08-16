# Task 13 Report: installer docs + dev launcher

## Status

**Complete.** Branch `local-app`. Not pushed.

## What changed

| File | Action |
|------|--------|
| `app/scripts/dev.ps1` | Created — starts uvicorn on `127.0.0.1:8787` and Vite `npm run dev` |
| `install.md` | Added `### Windows` section after the macOS brew block (winget ffmpeg, pip extras, skill junction, launcher) |
| `README.md` | Added short `### Local app (Windows)` under Manual install |

## Commit

```
docs: Windows install and local app launcher
```

Files committed: `install.md`, `README.md`, `app/scripts/dev.ps1` only. Did not commit `.env` or `.superpowers/`.

## Self-review

- [x] `dev.ps1` matches brief verbatim (ports 8787 / Vite default; no brew; no Scribe)
- [x] Windows section uses winget + junction + `powershell -File app\scripts\dev.ps1`
- [x] No brew in Windows section
- [x] README points at `install.md` and `app/scripts/dev.ps1` after `pip install -e ".[app]"`
- [x] Stayed on `local-app`; did not push

## Tests

No automated tests for docs/launcher. Static review only:

- Script resolves repo root via `$PSScriptRoot\..\..`
- Starts API with `--reload` then blocks on `npm run dev`
- Installs `node_modules` if missing

## Concerns

- `Start-Process -NoNewWindow` leaves uvicorn as a sibling process; stopping the shell may not kill it cleanly (acceptable for local dev per brief).
- README uses `".[app]"` while install.md Windows block uses `".[app,dev]"` — both match the brief; intentional difference.
- Launcher not executed end-to-end in this task (docs-only deliverable).
