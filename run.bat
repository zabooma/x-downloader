@echo off
setlocal

if not exist ".venv" (
    echo Virtual environment not found. Run install.bat first.
    exit /b 1
)

if "%X_BEARER_TOKEN%"=="" (
    if exist ".env" (
        for /f "usebackq eol=# tokens=1,* delims==" %%a in (".env") do set "%%a=%%b"
    )
)

.venv\Scripts\python x-downloader-app.py
