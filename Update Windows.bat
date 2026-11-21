@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0" || exit /b 1
rem Read this block before updating files, including this batch file.
(
    echo Close Z's Download Manager before updating.
    where py >nul 2>nul
    if errorlevel 1 (
        python update.py
    ) else (
        py -3 update.py
    )
    if errorlevel 1 (
        pause
        exit /b 1
    )
    pause
    exit /b 0
)
