# Single-process app. Prefer the Desktop shortcut (launch.cmd).
$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $root
& (Join-Path $PSScriptRoot "launch.cmd")
