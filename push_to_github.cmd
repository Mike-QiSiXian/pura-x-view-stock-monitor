@echo off
rem ============================================================
rem Push local commits (README.md etc.) to GitHub.
rem Run this OUTSIDE WorkBuddy: just double-click this file.
rem Reason: inside the WorkBuddy sandbox git-remote-https.exe crashes
rem         (exit 128, no output), so pushes must be done here.
rem ============================================================
cd /d "%~dp0"
title Push pura-x-view-stock-monitor to GitHub

echo [1/3] fetching remote ...
git fetch origin
if errorlevel 1 goto fail

echo [2/3] rebasing local commits onto remote ...
git -c rebase.autostash=true rebase origin/master
if errorlevel 1 goto fail

echo [3/3] pushing ...
git push origin master
if errorlevel 1 goto fail

echo.
echo DONE - remote is up to date. Recent commits:
git log --oneline -3
echo.
pause
exit /b 0

:fail
echo.
echo FAILED. Please run these three commands here and read the error message:
echo    git fetch origin
echo    git -c rebase.autostash=true rebase origin/master
echo    git push origin master
echo.
pause
exit /b 1
