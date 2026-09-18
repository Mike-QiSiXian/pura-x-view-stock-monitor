@echo off
rem Foreground launcher: shows live log output, press Ctrl+C to stop.
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PY=C:\Users\zhaozhe\.workbuddy\binaries\python\envs\default\Scripts\python.exe
if not exist "%PY%" (
  echo [ERROR] python venv not found at:
  echo   %PY%
  echo.
  echo Create it first with:
  echo   C:\Users\zhaozhe\.workbuddy\binaries\python\versions\3.13.12\python.exe -m venv C:\Users\zhaozhe\.workbuddy\binaries\python\envs\default
  echo   C:\Users\zhaozhe\.workbuddy\binaries\python\envs\default\Scripts\pip.exe install requests
  pause
  exit /b 1
)
title Pura X View Stock Monitor (foreground)
"%PY%" monitor.py
echo.
echo Monitor stopped. Press any key to close this window.
pause >nul
