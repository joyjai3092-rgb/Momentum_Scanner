@echo off
cd /d "%~dp0"
python --version >nul 2>&1
if errorlevel 1 (
  echo Python is not installed. Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
  pause
  exit /b
)
if not exist .venv python -m venv .venv
call .venv\Scripts\activate
python -m pip install -q -r requirements.txt
python -m pytest -q
echo.
echo If the last line says "passed" and nothing says "failed", everything is OK.
pause
