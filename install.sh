#!/bin/bash

set -e

echo "🚀 Kezdjük a szart, rendszerfrissítés..."
sudo pacman -Syu --noconfirm

echo "📦 Alap csomagok telepítése..."
sudo pacman -S --noconfirm \
    python \
    python-pip \
    python-virtualenv \
    ffmpeg \
    git \
    base-devel

echo "🐍 Python virtualenv létrehozása..."
if [ ! -d ".venv" ]; then
    python -m venv .venv
fi

source .venv/bin/activate

echo "📚 Python libraryk telepítése..."
pip install --upgrade pip

pip install \
    yt-dlp \
    spotipy \
    mutagen \
    requests \
    pillow \
    rich \
    questionary

echo "✅ Kész bazmeg!"
echo ""
echo "👉 Aktiváláshoz futtasd:"
echo "source .venv/bin/activate"
