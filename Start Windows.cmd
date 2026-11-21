@echo off
cd /d "%~dp0" || exit /b 1
if exist "Zs-Download-Manager.exe" (
    start "" "Zs-Download-Manager.exe"
    exit /b 0
)
where py >nul 2>nul
if errorlevel 1 (
    python app.py
) else (
    py -3 app.py
)
if errorlevel 1 pause
