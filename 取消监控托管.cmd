@echo off
rem ============================================================
rem Stop monitoring AND remove the scheduled task.
rem Double-click when you no longer need the stock monitor.
rem   1) deletes scheduled task PuraXViewMonitorGuard
rem   2) kills all running monitor.py processes
rem   3) removes monitor.pid
rem ============================================================
setlocal
cd /d "%~dp0"
title Remove Pura X View monitor auto-start

echo [1/3] deleting scheduled task PuraXViewMonitorGuard ...
schtasks /Delete /TN "PuraXViewMonitorGuard" /F
if errorlevel 1 echo     (task not found - already removed)

echo [2/3] stopping monitor processes ...
powershell -NoProfile -Command "$p = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*monitor.py*' -and $_.Name -like 'python*' }; if ($p) { $p | ForEach-Object { Write-Host ('    killing PID ' + $_.ProcessId); Stop-Process -Id $_.ProcessId -Force } } else { Write-Host '    no running monitor found' }"

echo [3/3] clearing monitor.pid ...
if exist monitor.pid del /q monitor.pid >nul 2>&1

echo.
echo Done. The monitor will not start again automatically.
echo (Cloud check on GitHub Actions is NOT affected - see 云端定时器配置说明.txt
echo  if you also want to stop it there.)
echo.
pause
endlocal
