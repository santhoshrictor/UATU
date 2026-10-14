# PowerShell Start Frontend Script
$ErrorActionPreference = "Stop"

$WorkspaceRoot = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location "$WorkspaceRoot\frontend"

Write-Host "=== Starting Frontend Dev Server on http://127.0.0.1:5173 ===" -ForegroundColor Cyan
npm run dev -- --host 127.0.0.1 --port 5173
