@echo off
setlocal

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python not found. Install Python 3.10+ from https://python.org
    exit /b 1
)

python -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python 3.10 or higher is required.
    python --version
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version') do echo Python %%v found.

echo Creating virtual environment...
python -m venv .venv

echo Installing dependencies...
.venv\Scripts\python -m pip install --upgrade pip --quiet
.venv\Scripts\pip install -r requirements.txt

echo.
echo Installation complete.
echo.
echo Run the app:  run.bat
echo.
echo Tip: set your bearer token as an environment variable to avoid
echo      entering it on every launch:
echo        set X_BEARER_TOKEN=your_token_here
echo      To make it permanent, add it via System Properties ^> Environment Variables.
