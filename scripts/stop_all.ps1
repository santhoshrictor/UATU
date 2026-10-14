# PowerShell Shutdown Script
$WorkspaceRoot = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $WorkspaceRoot

Write-Host "=== Stopping Development Processes ===" -ForegroundColor Yellow

# Stop Uvicorn & Vite if running
Get-Process | Where-Object { $_.ProcessName -match "uvicorn|node|vite" } | ForEach-Object {
    Write-Host "Stopping process $($_.ProcessName) (PID: $($_.Id))" -ForegroundColor Gray
    Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
}

# Stop PostgreSQL cleanly using pg_ctl
if (Test-Path "$WorkspaceRoot\.pgsql\pgsql\bin\pg_ctl.exe") {
    Write-Host "Stopping PostgreSQL database cleanly..." -ForegroundColor Yellow
    & "$WorkspaceRoot\.pgsql\pgsql\bin\pg_ctl.exe" -D "$WorkspaceRoot\.pgsql\data" stop -m fast
}

Write-Host "=== All Services Stopped Cleanly ===" -ForegroundColor Green
