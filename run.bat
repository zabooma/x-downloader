@echo off
setlocal

if not exist ".venv" (
    echo Virtual environment not found. Run install.bat first.
    exit /b 1
)

.venv\Scripts\python x-downloader-app.py
