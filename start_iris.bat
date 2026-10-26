@echo off
title UATU / IRIS AI - Master Launcher
echo ====================================================================
echo       INITIALIZING UATU VOICE ^& QUERY DECISION-SUPPORT CENTER
echo ====================================================================
echo.

:: Resolve project root directory
set "PROJECT_ROOT=%~dp0voice_agent"
if not exist "%PROJECT_ROOT%" (
    set "PROJECT_ROOT=%~dp0iris\jarvis_new"
)
if not exist "%PROJECT_ROOT%" (
    set "PROJECT_ROOT=%~dp0iris"
)
if not exist "%PROJECT_ROOT%" (
    set "PROJECT_ROOT=%~dp0"
)

:: Configure local python/uv environment
if exist "%PROJECT_ROOT%\.venv\Scripts\python.exe" (
    set "AGENT_CMD="%PROJECT_ROOT%\.venv\Scripts\python.exe" src\agent.py dev"
) else if exist "%PROJECT_ROOT%\.venv\Scripts\uv.exe" (
    set "AGENT_CMD="%PROJECT_ROOT%\.venv\Scripts\uv.exe" run python src\agent.py dev"
) else (
    set "AGENT_CMD=uv run python src\agent.py dev"
)

:: Ensure node, npm, and local venv paths are in PATH
set "PATH=%PROJECT_ROOT%\.venv\Scripts;%USERPROFILE%\.local\bin;%LOCALAPPDATA%\bin;C:\Program Files\nodejs;%PATH%"

echo [1/3] Starting IRIS / UATU Agent Backend Worker...
start "IRIS Backend Agent" cmd /k "cd /d "%PROJECT_ROOT%" && %AGENT_CMD%"

echo [2/3] Starting IRIS / UATU Command Center Frontend on port 3000...
start "IRIS Web Frontend" cmd /k "cd /d "%PROJECT_ROOT%\frontend" && npm.cmd run dev"

echo [3/3] Waiting for frontend server to bind to port 3000...
powershell -NoProfile -Command "for ($i=0; $i -lt 15; $i++) { try { $res = Invoke-WebRequest -Uri 'http://localhost:3000' -UseBasicParsing -TimeoutSec 1; if ($res.StatusCode -eq 200) { break } } catch {} Start-Sleep -Seconds 1 }"

echo.
echo [OK] Opening UATU Video Intelligence & IRIS AI Dashboard...
start http://localhost:5173

echo.
echo ====================================================================
echo   UATU VOICE ^& SEARCH ASSISTANT IS ONLINE!
echo   HUD Frontend: http://localhost:3000
echo   FastAPI UATU Backend: http://127.0.0.1:8000
echo   To shut down cleanly, double-click 'stop_iris.bat'.
echo ====================================================================
echo.
pause
