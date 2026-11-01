@echo off
cd /d "%~dp0"
python --version >nul 2>&1
if errorlevel 1 (
  echo Python is not installed. Install it from https://www.python.org/downloads/
  echo During install, TICK the box "Add python.exe to PATH". Then double-click this file again.
  pause
  exit /b
)
if not exist .venv python -m venv .venv
call .venv\Scripts\activate
python -m pip install -q -r requirements.txt
echo.
echo Opening the app in your browser. Keep this window open. Close it to stop the app.
python -m streamlit run app.py
pause
