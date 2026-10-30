$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

& $python -m engine.cli replay sample
Start-Process "http://127.0.0.1:8000"
& $python -m engine.cli serve
