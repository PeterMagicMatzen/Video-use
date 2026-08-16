### Task 13: installer docs + dev launcher

**Files:**
- Modify: `install.md`
- Create: `app/scripts/dev.ps1`
- Modify: `README.md` (short “Local app (Windows)” paragraph pointing at `install.md` and `app/scripts/dev.ps1`)

**Interfaces:**
- Consumes: ports and extras from the spec
- Produces: one command that starts both processes

- [ ] **Step 1: Write `app/scripts/dev.ps1`**

```powershell
$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $root

Start-Process -NoNewWindow -FilePath "python" -ArgumentList "-m", "uvicorn", "app.server.main:app", "--host", "127.0.0.1", "--port", "8787", "--reload"
Set-Location (Join-Path $root "app\web")
if (-not (Test-Path "node_modules")) { npm install }
npm run dev
```

- [ ] **Step 2: Add a Windows section to `install.md` after the macOS brew block**

```markdown
### Windows

```powershell
# ffmpeg full build (has libass / subtitles)
winget install Gyan.FFmpeg

# Python extras for the local app
cd $HOME\Developer\video-use
pip install -e ".[app,dev]"

# Skill junction (already present on this machine; recreate if needed)
New-Item -ItemType Junction -Path "$HOME\.claude\skills\video-use" -Target "$HOME\Developer\video-use" -Force

# Launch the local app
powershell -File app\scripts\dev.ps1
# UI: http://localhost:5173   API: http://127.0.0.1:8787
```

Do not use `brew`. Do not run Scribe as part of install.
```

- [ ] **Step 3: README paragraph**

Under Manual install, add 4 lines: Windows users can run the local app via `app/scripts/dev.ps1` after `pip install -e ".[app]"`.

- [ ] **Step 4: Commit**

```bash
git add install.md README.md app/scripts/dev.ps1
git commit -m "docs: Windows install and local app launcher"
```

---

