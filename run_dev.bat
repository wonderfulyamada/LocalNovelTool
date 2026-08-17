@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    echo .venv not found. Run dev_setup_and_run.bat first.
    pause
    exit /b 1
)
.venv\Scripts\python.exe main.py
