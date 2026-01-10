#!/bin/bash

set -e

echo "System update..."
sudo pacman -Syu --noconfirm

echo "Installing basic packages..."
sudo pacman -S --noconfirm \
    python \
    python-pip \
    python-virtualenv \
    ffmpeg \
    git \
    base-devel

echo "Creating Python virtualenv..."
if [ ! -d ".venv" ]; then
    python -m venv .venv
fi

source .venv/bin/activate

echo "Installing Python libraries..."
pip install --upgrade pip

pip install -r requirements.txt

echo "Done!"
echo ""
echo "To activate, run:"
echo "source .venv/bin/activate"
