#!/usr/bin/env bash
set -e

# Check Python is available
if ! command -v python3 &>/dev/null; then
    echo "Error: python3 not found. Install Python 3.10+ from https://python.org"
    exit 1
fi

# Check Python >= 3.10
if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)"; then
    echo "Error: Python 3.10 or higher is required."
    echo "Found: $(python3 --version)"
    exit 1
fi

echo "Python $(python3 --version | cut -d' ' -f2) found."

echo "Creating virtual environment..."
python3 -m venv .venv

echo "Installing dependencies..."
.venv/bin/pip install --upgrade pip --quiet
.venv/bin/pip install -r requirements.txt

echo ""
echo "Installation complete."
echo ""
echo "Run the app:  ./run.sh"
echo ""
echo "Tip: set your bearer token as an environment variable to avoid"
echo "     entering it on every launch:"
echo "       export X_BEARER_TOKEN=your_token_here"
echo "     Add that line to ~/.zshrc or ~/.bashrc to make it permanent."
