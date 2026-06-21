@echo off
setlocal

if not exist ".venv" (
    echo Virtual environment not found. Run install.bat first.
    exit /b 1
)

rem Load bearer token from .env file if present and not already set
if "%X_BEARER_TOKEN%"=="" (
    if exist ".env" (
        for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
            if not "%%a"=="" if not "%%a:~0,1%"=="#" set "%%a=%%b"
        )
    )
)

.venv\Scripts\python x-downloader-app.py
