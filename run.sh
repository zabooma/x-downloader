#!/usr/bin/env bash
set -e

if [ ! -d ".venv" ]; then
    echo "Virtual environment not found. Run ./install.sh first."
    exit 1
fi

# Load bearer token from .env file if present and not already set
if [ -z "$X_BEARER_TOKEN" ] && [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

source .venv/bin/activate
python x-downloader-app.py
