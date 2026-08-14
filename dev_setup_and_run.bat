@echo off
setlocal
cd /d "%~dp0"

if not exist .venv (
    py -m venv .venv
    if errorlevel 1 goto :error
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
if errorlevel 1 goto :error
pip install -r requirements.txt
if errorlevel 1 goto :error
python main.py
exit /b 0

:error
echo.
echo Setup or launch failed.
pause
exit /b 1
