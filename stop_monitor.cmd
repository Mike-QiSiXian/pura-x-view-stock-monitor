@echo off
rem Stops the background monitor started by run_monitor_hidden.cmd
cd /d "%~dp0"
if not exist monitor.pid (
  echo [INFO] monitor.pid not found - background monitor is probably not running.
  pause
  exit /b 0
)
set /p PID=<monitor.pid
echo Stopping monitor process PID %PID% ...
taskkill /f /pid %PID% >nul 2>&1
if errorlevel 1 (
  echo [WARN] Failed to kill PID %PID% - it may have already exited.
) else (
  echo [OK] Monitor stopped.
)
del /q monitor.pid >nul 2>&1
pause
