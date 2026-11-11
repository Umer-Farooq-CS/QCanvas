#!/usr/bin/env bash
# setup.sh — First-time installation script

set -e

echo "Installing system packages..."
sudo apt install -y nodejs npm python3-venv python3-full build-essential

# Python venv
if [ ! -d "venv" ]; then
    echo "Creating venv..."
    python3 -m venv venv
else
    echo "venv already exists"
fi

echo "Activating venv..."
source venv/bin/activate

echo "Upgrading pip..."
pip install --upgrade pip

# Python requirements
if [ -f "requirements.txt" ]; then
    echo "Installing Python requirements..."
    pip install -r requirements.txt
else
    echo "requirements.txt not found — skipping"
fi

# Frontend install
if [ -d "frontend" ]; then
    echo "Installing frontend dependencies..."
    cd frontend
    npm install
    cd ..
else
    echo "Frontend directory not found!"
fi

echo "Setup complete ✔"

