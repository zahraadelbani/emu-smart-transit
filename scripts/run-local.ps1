param([switch]$Setup)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$env:DEBUG = 'true'
$env:DEMO_MODE = 'true'
if ($Setup) {
    python -m pip install -r backend/requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed' }
    Push-Location frontend
    try { npm ci; if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed' } }
    finally { Pop-Location }
}
python backend/manage.py migrate
if ($LASTEXITCODE -ne 0) { throw 'Migration failed' }
python backend/manage.py seed_demo
if ($LASTEXITCODE -ne 0) { throw 'Demo seed failed' }
Write-Host 'Use two additional terminals (DEBUG=true, DEMO_MODE=true) for:'
Write-Host 'python backend/manage.py poll_gps --provider simulation'
Write-Host 'cd frontend; npm run dev'
python backend/manage.py runserver 127.0.0.1:8000
