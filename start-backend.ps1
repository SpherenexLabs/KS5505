$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $projectRoot "backend\venv\Scripts\python.exe"
$app = Join-Path $projectRoot "backend\app.py"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Backend Python environment not found: $python"
}

Write-Host "Starting CareBot backend with MediaPipe/OpenCV environment..."
Write-Host $python
& $python $app
