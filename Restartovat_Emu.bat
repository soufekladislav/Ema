@echo off
setlocal EnableExtensions
chcp 65001 >nul
title EMA HUB - oprava lokalni databaze a spusteni

set "EMA_DIR=C:\Users\ladis\Documents\GitHub\Ema"
set "EMA_PY=%EMA_DIR%\.venv\Scripts\python.exe"

echo ================================================
echo EMA HUB - oprava lokalni databaze a spusteni
echo ================================================
echo.
echo DULEZITE: pred spustenim zavri puvodni okno
 echo se serverem Ema, aby nebezely dva procesy.
echo.

if not exist "%EMA_DIR%\ema\web.py" (
  echo CHYBA: Nelze najit kod Emy v "%EMA_DIR%".
  goto :failed
)
if not exist "%EMA_PY%" (
  echo CHYBA: Nelze najit lokalni Python Emy: "%EMA_PY%".
  goto :failed
)
if not exist "%EMA_DIR%\.env" (
  echo CHYBA: Nelze najit lokalni .env Emy. Nic se nezmenilo.
  goto :failed
)

cd /d "%EMA_DIR%"
if errorlevel 1 goto :failed

echo [1/3] Bezpecna zaloha existujici SQLite databaze...
"%EMA_PY%" -c "import os,sqlite3,datetime; from dotenv import dotenv_values; from sqlalchemy.engine import make_url; u=make_url(dotenv_values('.env').get('DATABASE_URL','')); assert u.get_backend_name()=='sqlite', 'Tento spoustec je jen pro lokalni SQLite'; p=u.database; assert p and os.path.isfile(p), 'Databazovy soubor neexistuje - zkontroluj DATABASE_URL'; dst=p+'.backup_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'.sqlite'; src=sqlite3.connect(p); out=sqlite3.connect(dst); src.backup(out); out.close(); src.close(); print('Zaloha vytvorena:', os.path.abspath(dst))"
if errorlevel 1 (
  echo CHYBA: Zaloha se nepovedla. Databazova aktualizace nebyla spustena.
  goto :failed
)

echo.
echo [2/3] Doplnuji chybejici databazove tabulky a sloupce...
"%EMA_PY%" -m flask --app ema.web:create_app upgrade-db
if errorlevel 1 (
  echo CHYBA: Databazova aktualizace se nepovedla. Aplikaci nespoustim.
  goto :failed
)

echo.
echo [3/3] Spoustim Emu na http://127.0.0.1:5000
start "" "http://127.0.0.1:5000"
"%EMA_PY%" -m flask --app ema.web:create_app run --host 127.0.0.1 --port 5000

echo.
echo Ema byla ukoncena.
pause
exit /b 0

:failed
echo.
echo Zastaveno. Posli mi screenshot teto obrazovky.
pause
exit /b 1
