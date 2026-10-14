# PowerShell Setup Script - Workplace Video Intelligence Stage 1
$ErrorActionPreference = "Stop"

Write-Host "=== Setting up Workplace Video Intelligence (Stage 1 Foundation) ===" -ForegroundColor Cyan

$WorkspaceRoot = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $WorkspaceRoot

# 1. Virtual Environment
if (-not (Test-Path "$WorkspaceRoot\backend\.venv")) {
    Write-Host "[1/4] Creating Python 3.12 virtual environment..." -ForegroundColor Yellow
    py -3.12 -m venv "$WorkspaceRoot\backend\.venv"
} else {
    Write-Host "[1/4] Python virtual environment exists." -ForegroundColor Green
}

# 2. Python Dependencies
Write-Host "[2/4] Installing Python requirements..." -ForegroundColor Yellow
& "$WorkspaceRoot\backend\.venv\Scripts\python.exe" -m pip install -r "$WorkspaceRoot\backend\requirements.txt"

# 3. Database Check
Write-Host "[3/4] Checking PostgreSQL..." -ForegroundColor Yellow
$PgReady = & "$WorkspaceRoot\.pgsql\pgsql\bin\pg_isready.exe" -h 127.0.0.1 -p 5432 -U postgres 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "PostgreSQL is not running on port 5432. Please start it using scripts\start_backend.ps1" -ForegroundColor Yellow
} else {
    Write-Host "PostgreSQL is online. Applying migrations to workplace_dev..." -ForegroundColor Green
    & "$WorkspaceRoot\backend\.venv\Scripts\python.exe" -m alembic -c "$WorkspaceRoot\alembic.ini" upgrade head
}

# 4. Frontend Dependencies
Write-Host "[4/4] Installing Frontend dependencies..." -ForegroundColor Yellow
Set-Location "$WorkspaceRoot\frontend"
npm install
Set-Location $WorkspaceRoot

Write-Host "=== Setup Complete. Run scripts\start_backend.ps1 and scripts\start_frontend.ps1 to launch. ===" -ForegroundColor Green
