@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0" || exit /b 1
echo Close Z's Download Manager before updating.
rem Read this block before source updates can replace this batch file.
(
    if exist "Zs-Download-Manager.exe" (
        powershell.exe -NoProfile -Command "$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'; $name='Zs-Download-Manager.exe'; $target=Join-Path (Get-Location) $name; $temp=$target+'.'+[guid]::NewGuid().ToString('N')+'.tmp'; try { $release=Invoke-RestMethod 'https://api.github.com/repos/Zyvelia/DownloadManager/releases/latest'; $asset=$release.assets | Where-Object { $_.name -eq $name } | Select-Object -First 1; if (-not $asset -or $asset.digest -notmatch '^sha256:[0-9a-fA-F]{64}$') { throw 'The latest release has no verified Windows executable.' }; if ((Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash -eq $asset.digest.Substring(7)) { Write-Host 'Already up to date.'; exit 0 }; Invoke-WebRequest -UseBasicParsing -Uri $asset.browser_download_url -OutFile $temp; if ((Get-FileHash -Algorithm SHA256 -LiteralPath $temp).Hash -ne $asset.digest.Substring(7)) { throw 'The update checksum does not match.' }; $backup=$temp+'.bak'; [IO.File]::Replace($temp,$target,$backup); Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue; Write-Host 'Update installed.' } catch { Write-Host ('Update failed: '+$_.Exception.Message); exit 1 } finally { if (Test-Path -LiteralPath $temp) { Remove-Item -LiteralPath $temp -Force } }"
    ) else (
        where py >nul 2>nul
        if errorlevel 1 (
            python update.py
        ) else (
            py -3 update.py
        )
    )
    if errorlevel 1 (
        pause
        exit /b 1
    )
    pause
    exit /b 0
)
