$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$venvPython = Join-Path $root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
  Write-Host "Creating Python virtualenv..."
  python -m venv (Join-Path $root "backend\.venv")
}
& $venvPython -m pip install -r (Join-Path $root "backend\requirements.txt")

if (-not (Test-Path (Join-Path $root "frontend\node_modules"))) {
  Write-Host "Installing Angular dependencies..."
  npm --prefix (Join-Path $root "frontend") install
}

Write-Host "Starting API on :8000 and Angular on :4200"
Start-Process -FilePath $venvPython -ArgumentList "-m","uvicorn","app.main:app","--reload","--port","8000" -WorkingDirectory (Join-Path $root "backend")
Set-Location (Join-Path $root "frontend")
npm start
