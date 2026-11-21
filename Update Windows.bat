@echo off
setlocal EnableDelayedExpansion
rem Read this block before updating files, including this batch file.
(
    cd /d "%~dp0" || exit /b 1
    echo Close Z's Download Manager before updating.
    where py >nul 2>nul
    if errorlevel 1 (
        python "%~dp0update.py"
    ) else (
        py -3 "%~dp0update.py"
    )
    set "update_result=!ERRORLEVEL!"
    pause
    exit /b !update_result!
)
