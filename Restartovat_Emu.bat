@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Restart Ema - Fresh Crackers

if not exist ".venv\Scripts\python.exe" (
    echo CHYBA: Tento soubor musi byt ve slozce Ema vedle .venv.
    echo Hledano: %CD%\.venv\Scripts\python.exe
    pause
    exit /b 1
)

if not exist "ema\web.py" (
    echo CHYBA: Ve slozce chybi ema\web.py.
    pause
    exit /b 1
)

echo Restartuji lokalni Emu na http://127.0.0.1:5000

rem Kill only Python processes running this specific Flask application.
powershell -NoProfile -Command "$processes = Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('python.exe','pythonw.exe') -and $_.CommandLine -like '*ema.web:create_app*' }; foreach ($p in $processes) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }"
if errorlevel 1 (
    echo Nepodarilo se overit bezici procesy. Zkontroluj Spravce uloh.
    pause
    exit /b 1
)

timeout /t 2 /nobreak >nul

rem Do not interfere with a different application that owns port 5000.
powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue) { exit 1 }"
if errorlevel 1 (
    echo Port 5000 je stale obsazeny. Nebyla spustena dalsi kopie Emy.
    echo Zkontroluj Spravce uloh nebo aplikaci na portu 5000.
    pause
    exit /b 1
)

rem Starts in a separate window: no need to type commands.
start "EMA HUB" ".venv\Scripts\python.exe" -m flask --app ema.web:create_app run --host 127.0.0.1 --port 5000
if errorlevel 1 (
    echo Nepodarilo se spustit Emu.
    pause
    exit /b 1
)

echo Ema se spousti v samostatnem okne. V prohlizeci otevri http://127.0.0.1:5000
exit /b 0
