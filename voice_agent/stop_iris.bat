@echo off
title UATU AI - Shutdown
echo ====================================================================
echo                      SHUTTING DOWN UATU AI
echo ====================================================================
echo.
echo Stopping services on port 3000 and background agent...

:: Kill processes holding port 3000 (Next.js server)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":3000"') do (
    taskkill /f /pid %%a >nul 2>&1
)

:: Terminate cmd windows
taskkill /f /fi "WINDOWTITLE eq UATU Backend Agent*" >nul 2>&1
taskkill /f /fi "WINDOWTITLE eq UATU Web Frontend*" >nul 2>&1
taskkill /f /fi "WINDOWTITLE eq IRIS Backend Agent*" >nul 2>&1
taskkill /f /fi "WINDOWTITLE eq IRIS Web Frontend*" >nul 2>&1

:: Clean up agent.py processes if running in background
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*agent.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1

echo.
echo [OK] All UATU AI services have been stopped cleanly.
echo ====================================================================
timeout /t 3 /nobreak >nul
