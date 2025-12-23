import os
import subprocess
import threading
from pathlib import Path
import re
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# --- Alapbeállítások és stílus ---
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

BASE_DIR = Path.home() / "MusicDownloader"
BASE_DIR.mkdir(exist_ok=True)

class MusicDownloaderGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Zeneletöltő - Modern GUI")
        self.geometry("600x550")

        # UI elemek felépítése
        self.setup_ui()

    def setup_ui(self):
        """Létrehozza a grafikus felület elemeit."""
        self.grid_columnconfigure(0, weight=1)

        # Főcím
        self.label = ctk.CTkLabel(self, text="Zeneletöltő Pro", font=ctk.CTkFont(size=26, weight="bold"))
        self.label.pack(pady=(30, 20))

        # Link bemeneti mező
        self.link_label = ctk.CTkLabel(self, text="Spotify Playlist vagy YouTube Link:")
        self.link_label.pack(pady=(10, 0))

        self.link_entry = ctk.CTkEntry(self, placeholder_text="Illeszd be a linket ide...", width=480)
        self.link_entry.pack(pady=10)

        # Minőség választó (a beküldött logikád alapján)
        self.quality_label = ctk.CTkLabel(self, text="Válassz minőséget:")
        self.quality_label.pack(pady=(10, 0))

        self.quality_options = ["MP3 128kb", "MP3 320kb", "FLAC"]
        self.quality_var = ctk.StringVar(value="MP3 320kb")
        self.quality_dropdown = ctk.CTkOptionMenu(self, values=self.quality_options, variable=self.quality_var)
        self.quality_dropdown.pack(pady=10)

        # Letöltés gomb
        self.download_btn = ctk.CTkButton(
            self,
            text="Letöltés Indítása",
            command=self.start_download_thread,
            fg_color="#1DB954", # Spotify zöld
            hover_color="#18a34a",
            font=ctk.CTkFont(weight="bold")
        )
        self.download_btn.pack(pady=30)

        # Eseménynapló (Log)
        self.log_text = ctk.CTkTextbox(self, width=500, height=180, font=ctk.CTkFont(family="Consolas", size=12))
        self.log_text.pack(pady=10)
        self.log_text.insert("0.0", "Rendszer készen áll...\n")
        self.log_text.configure(state="disabled")

    def log(self, message):
        """Üzenet kiírása a log ablakba."""
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"> {message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    # --- Zeneletöltő Logika ---

    def init_spotify(self):
        """Spotify kliens inicializálása környezeti változókból."""
        cid = os.getenv("SPOTIFY_CLIENT_ID")
        secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        if not cid or not secret:
            return None
        return spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=cid, client_secret=secret))

    def get_spotify_tracks(self, sp, url):
        """Összes szám lekérése a playlistből lapozással."""
        tracks = []
        try:
            results = sp.playlist_items(url, additional_types=["track"])
            while results:
                for item in results["items"]:
                    track = item.get("track")
                    if track:
                        tracks.append({
                            "title": track["name"],
                            "artist": track["artists"][0]["name"]
                        })
                results = sp.next(results) if results["next"] else None
        except Exception as e:
            self.log(f"Spotify hiba: {e}")
        return tracks

    def download_audio(self, query, quality_cfg, out_dir):
        """A yt-dlp hívása a letöltéshez."""
        url_or_search = query
        if not re.match(r'https?://', query):
            url_or_search = f"ytsearch1:{query}"
        elif "music.youtube.com" in query:
            url_or_search = query.replace("music.youtube.com", "www.youtube.com")

        cmd = [
            "yt-dlp",
            url_or_search,
            "-x",
            "--audio-format", quality_cfg["format"],
            "--audio-quality", quality_cfg["bitrate"],
            "--embed-metadata",
            "--no-playlist",
            "-o", str(out_dir / "%(title)s.%(ext)s")
        ]

        # A háttérben futtatjuk, a kimenetet nem várjuk meg részletesen
        subprocess.run(cmd, capture_output=True)

    def start_download_thread(self):
        """Gombnyomásra elindítja a letöltést egy külön szálon."""
        self.download_btn.configure(state="disabled")
        thread = threading.Thread(target=self.process_download, daemon=True)
        thread.start()

    def process_download(self):
        """A tényleges letöltési folyamat menedzselése."""
        link = self.link_entry.get().strip()
        if not link:
            messagebox.showwarning("Figyelem", "Üres a link mező!")
            self.download_btn.configure(state="normal")
            return

        # Minőség beállítása
        quality_map = {
            "MP3 128kb": {"format": "mp3", "bitrate": "128K"},
            "MP3 320kb": {"format": "mp3", "bitrate": "320K"},
            "FLAC": {"format": "flac", "bitrate": "0"}
        }
        quality = quality_map[self.quality_var.get()]

        playlist_dir = BASE_DIR / "Downloaded"
        playlist_dir.mkdir(exist_ok=True)

        # Spotify link felismerése
        if "open.spotify.com" in link:
            self.log("Spotify link észlelve. Kapcsolódás...")
            sp = self.init_spotify()

            if not sp:
                self.log("HIBA: Hiányzó Spotify API kulcsok!")
                messagebox.showerror("Hiba", "Nincsenek beállítva a környezeti változók (SPOTIFY_CLIENT_ID / SECRET)!")
            else:
                tracks = self.get_spotify_tracks(sp, link)
                self.log(f"{len(tracks)} zeneszám beolvasva. Letöltés indul...")

                for i, track in enumerate(tracks, 1):
                    search_str = f"{track['artist']} - {track['title']}"
                    self.log(f"[{i}/{len(tracks)}] Letöltés: {search_str}")
                    self.download_audio(search_str, quality, playlist_dir)

                self.log("Minden Spotify szám kész!")

        # YouTube link felismerése
        elif "youtube.com" in link or "youtu.be" in link:
            self.log("YouTube link észlelve. Letöltés...")
            self.download_audio(link, quality, playlist_dir)
            self.log("Letöltés befejezve!")

        else:
            self.log("Ismeretlen link, keresésként kezelem...")
            self.download_audio(link, quality, playlist_dir)
            self.log("Keresés és letöltés kész!")

        self.log(f"Fájlok helye: {playlist_dir}")
        self.download_btn.configure(state="normal")
        messagebox.showinfo("Kész", "A művelet sikeresen befejeződött!")

if __name__ == "__main__":
    app = MusicDownloaderGUI()
    app.mainloop()
