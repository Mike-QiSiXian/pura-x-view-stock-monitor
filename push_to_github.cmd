@echo off
setlocal
cd /d "%~dp0"
title Push pura-x-view-stock-monitor to GitHub

echo Step 1: fetch remote ...
git fetch origin

echo Step 2: rebase local commits onto remote ...
git -c rebase.autostash=true rebase origin/master
rem If the auto-stash could not be re-applied (stock_state.json clash),
rem git keeps it in the stash. Drop it: the monitor regenerates that file.
git stash drop >nul 2>&1

echo Step 3: push ...
git push origin master
if not errorlevel 1 goto done

echo.
echo Push rejected - remote moved meanwhile, retrying once with fresh rebase ...
git fetch origin
git -c rebase.autostash=true rebase origin/master
git stash drop >nul 2>&1
git push origin master
if not errorlevel 1 goto done

echo.
echo STILL FAILING. Please copy the last error message to your assistant.
echo.
pause
exit /b 1

:done
echo.
echo SUCCESS - remote is up to date. Latest commits:
git log --oneline -3
echo.
pause
endlocal
