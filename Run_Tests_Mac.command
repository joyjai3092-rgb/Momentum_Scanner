#!/bin/bash
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python is not installed. Install it from https://www.python.org/downloads/ then double-click this file again."
  read -p "Press Enter to close"; exit 1
fi
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
python -m pip install -q -r requirements.txt
python -m pytest -q
echo
echo 'If the last line says "passed" and nothing says "failed", everything is OK.'
read -p "Press Enter to close"
