# PowerShell Test Runner Script
$ErrorActionPreference = "Stop"

$WorkspaceRoot = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $WorkspaceRoot

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "STAGE 1 FOUNDATION VERIFICATION SUITE" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Run Backend Tests
Write-Host "`n[1/3] Running Backend & Real PostgreSQL Integration Tests..." -ForegroundColor Yellow
& "$WorkspaceRoot\backend\.venv\Scripts\python.exe" -m pytest "$WorkspaceRoot\backend\tests" -v
if ($LASTEXITCODE -ne 0) {
    Write-Host "Backend tests failed!" -ForegroundColor Red
    exit 1
}

# 2. Run Frontend Type Checking
Write-Host "`n[2/3] Running Frontend TypeScript Typecheck..." -ForegroundColor Yellow
Set-Location "$WorkspaceRoot\frontend"
npx tsc --noEmit
if ($LASTEXITCODE -ne 0) {
    Write-Host "Frontend type check failed!" -ForegroundColor Red
    exit 1
}

# 3. Run Frontend Production Build
Write-Host "`n[3/3] Running Frontend Production Build..." -ForegroundColor Yellow
npm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "Frontend build failed!" -ForegroundColor Red
    exit 1
}

Set-Location $WorkspaceRoot
Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "ALL STAGE 1 AUTOMATED CHECKS PASSED SUCCESSFULLY" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
