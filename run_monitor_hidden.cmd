@echo off
rem Background launcher: no console window. Logs go to stock_monitor.log
rem Stop it with stop_monitor.cmd
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PYW=C:\Users\zhaozhe\.workbuddy\binaries\python\envs\default\Scripts\pythonw.exe
if not exist "%PYW%" (
  echo [ERROR] pythonw.exe not found at:
  echo   %PYW%
  echo See run_monitor.cmd for venv setup instructions.
  pause
  exit /b 1
)
start "" "%PYW%" monitor.py
echo Monitor started in background (no window).
echo Check progress:  stock_monitor.log
echo Stop it with:    stop_monitor.cmd
timeout /t 5 >nul
