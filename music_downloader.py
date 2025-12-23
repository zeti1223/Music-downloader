import os
import subprocess
from pathlib import Path
import re

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from rich.console import Console
from rich.progress import Progress
import questionary

console = Console()

BASE_DIR = Path.home() / "MusicDownloader"
BASE_DIR.mkdir(exist_ok=True)

# =====================
# Spotify init
# =====================
def init_spotify():
    cid = os.getenv("SPOTIFY_CLIENT_ID")
    secret = os.getenv("SPOTIFY_CLIENT_SECRET")

    if not cid or not secret:
        console.print("[bold red]Hiányzó Spotify env változók, bazmeg[/bold red]")
        exit(1)

    return spotipy.Spotify(
        auth_manager=SpotifyClientCredentials(
            client_id=cid,
            client_secret=secret
        )
    )

# =====================
# Spotify playlist (pagination!)
# =====================
def get_all_spotify_tracks(sp, playlist_url):
    tracks = []
    results = sp.playlist_items(playlist_url, additional_types=["track"])

    while results:
        for item in results["items"]:
            track = item.get("track")
            if not track:
                continue

            tracks.append({
                "title": track["name"],
                "artist": track["artists"][0]["name"],
                "album": track["album"]["name"],
                "year": track["album"]["release_date"][:4]
            })

        if results["next"]:
            results = sp.next(results)
        else:
            results = None

    return tracks

# =====================
# YouTube Music vagy keresés
# =====================
def is_youtube_link(url: str):
    return "youtube.com" in url or "youtu.be" in url or "music.youtube.com" in url

def fix_youtube_music_link(url: str):
    if "music.youtube.com" in url:
        return url.replace("music.youtube.com", "www.youtube.com")
    return url

# =====================
# yt-dlp letöltés
# =====================
def download_audio(query, quality, out_dir):
    url_or_search = query
    if not re.match(r'https?://', query):
        # nem link -> keresés
        url_or_search = f"ytsearch1:{query}"
    else:
        url_or_search = fix_youtube_music_link(query)

    cmd = [
        "yt-dlp",
        url_or_search,
        "-x",
        "--audio-format", quality["format"],
        "--audio-quality", quality["bitrate"],
        "--embed-metadata",
        "--no-playlist",
        "-o", str(out_dir / "%(title)s.%(ext)s")
    ]

    try:
        # check=True hogy hibát dobjon, látszódjon
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Hiba a letöltésnél: {e}[/red]")

# =====================
# Fő logika
# =====================
def main():
    console.print("\n[bold green]Zeneletöltő szar elindult[/bold green]\n")

    link = questionary.text(
        "Spotify playlist vagy YouTube Music linket ide, ne tökölj:"
    ).ask()

    quality_choice = questionary.select(
        "Milyen minőséget akarsz, te válogatós geci?",
        choices=[
            "MP3 128kb",
            "MP3 320kb",
            "FLAC"
        ]
    ).ask()

    quality_map = {
        "MP3 128kb": {"format": "mp3", "bitrate": "128K"},
        "MP3 320kb": {"format": "mp3", "bitrate": "320K"},
        "FLAC": {"format": "flac", "bitrate": "0"}
    }

    quality = quality_map[quality_choice]

    playlist_dir = BASE_DIR / "Downloaded"
    playlist_dir.mkdir(exist_ok=True)

    if "spotify.com" in link:
        sp = init_spotify()
        tracks = get_all_spotify_tracks(sp, link)
        console.print(f"[cyan]{len(tracks)} track megtalálva Spotify playlistből[/cyan]")

        with Progress() as progress:
            task = progress.add_task("Letöltés mint a kurvaélet...", total=len(tracks))

            for track in tracks:
                search = f"{track['artist']} - {track['title']}"
                download_audio(search, quality, playlist_dir)
                progress.advance(task)

    elif is_youtube_link(link):
        console.print("[cyan]YouTube Music / YouTube link észlelve, kezdődik a letöltés[/cyan]")
        download_audio(link, quality, playlist_dir)

    else:
        console.print("[red]Hülye link, semmi értelme[/red]")
        return

    console.print(f"\n[bold magenta]Kész. A letöltések itt vannak: {playlist_dir}[/bold magenta]\n")

if __name__ == "__main__":
    main()
