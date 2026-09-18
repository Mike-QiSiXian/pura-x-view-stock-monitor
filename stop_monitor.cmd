@echo off
rem Stops ALL running Pura X View monitor instances (background or foreground).
rem Matches by command line containing monitor.py, so other Python processes are not touched.
setlocal
cd /d "%~dp0"
echo Stopping Pura X View monitor instances ...
powershell -NoProfile -Command "$p = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*monitor.py*' -and $_.Name -like 'python*' }; if ($p) { $p | ForEach-Object { Write-Host ('  killing PID ' + $_.ProcessId); Stop-Process -Id $_.ProcessId -Force } } else { Write-Host '  no running monitor found' }"
if exist monitor.pid del /q monitor.pid >nul 2>&1
echo Done. PID file cleared.
pause
