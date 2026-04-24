# Install system dependencies on Windows via winget, then bootstrap Python + Node.
# Run from an elevated PowerShell. Requires winget.
$ErrorActionPreference = 'Stop'
$ProjRoot = Resolve-Path "$PSScriptRoot\.."
Set-Location $ProjRoot

function Need($id, $label) {
  Write-Host "[install_windows] ensuring $label..."
  winget install --id $id -e --accept-package-agreements --accept-source-agreements -h 2>$null
}

Need "Python.Python.3.11" "Python 3.11"
Need "OpenJS.NodeJS.LTS" "Node.js LTS"
Need "Ollama.Ollama" "Ollama"
Need "UB-Mannheim.TesseractOCR" "Tesseract OCR"
Need "Gyan.FFmpeg" "FFmpeg"

py -3.11 -m venv .venv
. .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip wheel
pip install -e backend
pip install -e "backend[dev]"

Set-Location frontend
npm install
Set-Location $ProjRoot

if (-not (Test-Path .env)) { Copy-Item .env.example .env }

Write-Host "[install_windows] done. Next: scripts\pull_models.ps1 (or run scripts\dev.ps1)."
