# PowerShell Start Backend Script
$ErrorActionPreference = "Stop"

$WorkspaceRoot = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $WorkspaceRoot

Write-Host "=== Starting Backend Services (Stage 1 Foundation) ===" -ForegroundColor Cyan

# 1. Ensure PostgreSQL is running
$PgReady = & "$WorkspaceRoot\.pgsql\pgsql\bin\pg_isready.exe" -h 127.0.0.1 -p 5432 -U postgres 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Starting local PostgreSQL server on 127.0.0.1:5432..." -ForegroundColor Yellow
    Start-Process -FilePath "$WorkspaceRoot\.pgsql\pgsql\bin\postgres.exe" -ArgumentList "-D", "$WorkspaceRoot\.pgsql\data", "-p", "5432" -WindowStyle Hidden
    Start-Sleep -Seconds 2
}
Write-Host "PostgreSQL is accepting connections on 127.0.0.1:5432" -ForegroundColor Green

# 2. Ensure migrations are up to date
Write-Host "Applying database migrations to workplace_dev..." -ForegroundColor Cyan
& "$WorkspaceRoot\backend\.venv\Scripts\python.exe" -m alembic -c "$WorkspaceRoot\alembic.ini" upgrade head

# 3. Start FastAPI application
Write-Host "Starting FastAPI Backend on http://127.0.0.1:8000 (Ctrl+C to exit)..." -ForegroundColor Green
& "$WorkspaceRoot\backend\.venv\Scripts\python.exe" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
