$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $root

Start-Process -NoNewWindow -FilePath "python" -ArgumentList "-m", "uvicorn", "app.server.main:app", "--host", "127.0.0.1", "--port", "8787", "--reload"
Set-Location (Join-Path $root "app\web")
if (-not (Test-Path "node_modules")) { npm install }
npm run dev
