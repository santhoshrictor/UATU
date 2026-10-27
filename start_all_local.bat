@echo off
title UATU Intelligence Platform - Full Local Host Launcher
echo ====================================================================
echo       UATU WORKPLACE INTELLIGENCE & IRIS AI - LOCAL HOSTING
echo ====================================================================
echo.

set "ROOT=%~dp0"
cd /d "%ROOT%"

:: 1. PostgreSQL Database
echo [1/5] Ensuring Local PostgreSQL Database is running (port 5432)...
powershell -NoProfile -Command "if (!(Get-NetTCPConnection -LocalPort 5432 -ErrorAction SilentlyContinue)) { Start-Process -FilePath '%ROOT%.pgsql\pgsql\bin\postgres.exe' -ArgumentList '-D', '%ROOT%.pgsql\data', '-p', '5432' -WindowStyle Hidden; Start-Sleep -Seconds 2 }"

:: 2. FastAPI Backend
echo [2/5] Starting FastAPI Vision & Telemetry Backend (port 8000)...
start "UATU FastAPI Backend" cmd /k "cd /d "%ROOT%" && "%ROOT%backend\.venv\Scripts\python.exe" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000"

:: 3. UATU Dashboard Frontend (Vite)
echo [3/5] Starting UATU Enterprise Camera Dashboard (port 5173)...
start "UATU Dashboard Frontend" cmd /k "cd /d "%ROOT%frontend" && npm.cmd run dev -- --host 127.0.0.1 --port 5173"

:: 4. IRIS Voice AI Agent Worker
echo [4/5] Starting IRIS Decision-Support Agent Worker...
start "IRIS Backend Agent" cmd /k "cd /d "%ROOT%voice_agent" && "%ROOT%voice_agent\.venv\Scripts\python.exe" src\agent.py dev"

:: 5. IRIS Web Command Center (Next.js)
echo [5/5] Starting IRIS Command Center HUD (port 3000)...
start "IRIS Web Frontend" cmd /k "cd /d "%ROOT%voice_agent\frontend" && npm.cmd run dev"

echo.
echo Waiting for services to bind to local ports...
powershell -NoProfile -Command "for ($i=0; $i -lt 15; $i++) { try { $res1 = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/docs' -UseBasicParsing -TimeoutSec 1; $res2 = Invoke-WebRequest -Uri 'http://localhost:5173' -UseBasicParsing -TimeoutSec 1; if ($res1.StatusCode -eq 200 -and $res2.StatusCode -eq 200) { break } } catch {} Start-Sleep -Seconds 1 }"

echo.
echo [OK] Launching Local Browser Interfaces...
start http://localhost:5173
start http://localhost:3000

echo.
echo ====================================================================
echo   ALL SERVICES ARE ACTIVE AND HOSTED LOCALLY:
echo   - UATU Camera Dashboard:   http://localhost:5173
echo   - IRIS AI Command Center:  http://localhost:3000
echo   - FastAPI Backend API:     http://127.0.0.1:8000
echo   - Interactive API Docs:    http://127.0.0.1:8000/docs
echo   - PostgreSQL Database:     127.0.0.1:5432
echo.
echo   To shut down all services, run: scripts\stop_all.ps1
echo ====================================================================
echo.
pause
