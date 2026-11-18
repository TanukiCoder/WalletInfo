@echo off
setlocal EnableExtensions
rem WalletInfo — Windows
rem Developer: TG: @TanukiCode / Site: Tanuki.host
rem Telegram: https://t.me/TanukiCode
rem Site: https://tanuki.host
cd /d "%~dp0"
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PIP_DISABLE_PIP_VERSION_CHECK=1"

if "%~1"=="" (
  echo Использование: info.bat ^<private_key_hex^> [аргументы info.py]
  echo Пример: info.bat 0xYOUR_KEY
  exit /b 1
)

set "PYLAUNCH="
where py >nul 2>&1 && set "PYLAUNCH=py -3"
if not defined PYLAUNCH (
  where python >nul 2>&1 && set "PYLAUNCH=python"
)
if not defined PYLAUNCH (
  echo Не найден Python 3.10+. Установите с https://www.python.org/downloads/ и отметьте "Add python.exe to PATH".
  exit /b 1
)

%PYLAUNCH% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 (
  echo Нужен Python 3.10 или новее.
  exit /b 1
)

if not exist "venv\Scripts\python.exe" (
  echo Создаю venv...
  %PYLAUNCH% -m venv venv
  if errorlevel 1 (
    echo Не удалось создать venv. Переустановите Python с python.org, не из Microsoft Store.
    exit /b 1
  )
)

venv\Scripts\python.exe -m pip install --timeout 60 -r requirements.txt
if errorlevel 1 (
  echo Не удалось поставить зависимости. Проверьте интернет и повторите запуск.
  exit /b 1
)

venv\Scripts\python.exe info.py %*
exit /b %ERRORLEVEL%
