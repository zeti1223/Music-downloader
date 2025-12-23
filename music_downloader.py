import os
import subprocess
import threading
from pathlib import Path
import re
import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv

# .env betöltése
load_dotenv()

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class MusicDownloaderGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Zeneletöltő Pro - Single & Playlist Support")
        self.geometry("700x650")

        # Konfigurációk
        self.download_path = tk.StringVar(value=str(Path.home() / "MusicDownloader" / "Downloaded"))
        self.quality_var = tk.StringVar(value="MP3 320kb")

        self.quality_map = {
            "MP3 128kb": {"format": "mp3", "bitrate": "128K", "args": []},
            "MP3 320kb": {"format": "mp3", "bitrate": "320K", "args": []},
            "FLAC": {"format": "flac", "bitrate": "0", "args": []},
            "WAV 48kHz 24bit": {
                "format": "wav",
                "bitrate": None,
                "args": ["--postprocessor-args", "ffmpeg:-ar 48000 -sample_fmt s32"]
            }
        }

        self.setup_ui()

    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")

        self.tab_main = self.tabview.add("Letöltés")
        self.tab_settings = self.tabview.add("Beállítások")

        self.setup_main_tab()
        self.setup_settings_tab()

    def setup_main_tab(self):
        self.label = ctk.CTkLabel(self.tab_main, text="Zeneletöltő", font=ctk.CTkFont(size=22, weight="bold"))
        self.label.pack(pady=20)

        self.link_entry = ctk.CTkEntry(self.tab_main, placeholder_text="Spotify (track/playlist) vagy YouTube link...", width=500)
        self.link_entry.pack(pady=10)

        self.download_btn = ctk.CTkButton(
            self.tab_main, text="Letöltés Indítása",
            command=self.start_download_thread,
            fg_color="#1DB954", hover_color="#18a34a"
        )
        self.download_btn.pack(pady=20)

        self.log_text = ctk.CTkTextbox(self.tab_main, width=550, height=280, font=ctk.CTkFont(family="Consolas", size=12))
        self.log_text.pack(pady=10)
        self.log_text.configure(state="disabled")

    def setup_settings_tab(self):
        ctk.CTkLabel(self.tab_settings, text="Letöltési mappa:", font=ctk.CTkFont(weight="bold")).pack(pady=(20, 5))
        path_frame = ctk.CTkFrame(self.tab_settings, fg_color="transparent")
        path_frame.pack(fill="x", padx=40)
        self.path_entry = ctk.CTkEntry(path_frame, textvariable=self.download_path, width=350)
        self.path_entry.pack(side="left", padx=5)
        self.browse_btn = ctk.CTkButton(path_frame, text="Tallózás", width=80, command=self.browse_folder)
        self.browse_btn.pack(side="left")

        ctk.CTkLabel(self.tab_settings, text="Minőség:", font=ctk.CTkFont(weight="bold")).pack(pady=(30, 5))
        self.quality_dropdown = ctk.CTkOptionMenu(self.tab_settings, values=list(self.quality_map.keys()), variable=self.quality_var)
        self.quality_dropdown.pack(pady=10)

    def browse_folder(self):
        new_path = filedialog.askdirectory()
        if new_path:
            self.download_path.set(new_path)

    def log(self, message):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"> {message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    # --- Logika ---

    def init_spotify(self):
        cid = os.getenv("SPOTIFY_CLIENT_ID")
        secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        if not cid or not secret:
            return None
        return spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=cid, client_secret=secret))

    def get_spotify_content(self, sp, url):
        """Kezeli a playlisteket és az egyedülálló trackeket is."""
        tracks = []
        try:
            if "/track/" in url:
                track = sp.track(url)
                tracks.append({"title": track["name"], "artist": track["artists"][0]["name"]})
            elif "/playlist/" in url:
                results = sp.playlist_items(url, additional_types=["track"])
                while results:
                    for item in results["items"]:
                        t = item.get("track")
                        if t:
                            tracks.append({"title": t["name"], "artist": t["artists"][0]["name"]})
                    results = sp.next(results) if results["next"] else None
            else:
                self.log("Ismeretlen Spotify link típus!")
        except Exception as e:
            self.log(f"Spotify hiba: {e}")
        return tracks

    def download_audio(self, query, quality_cfg, out_dir):
        # YouTube Music link fixálás
        url_or_search = query
        if not re.match(r'https?://', query):
            url_or_search = f"ytsearch1:{query}"
        elif "music.youtube.com" in query:
            url_or_search = query.replace("music.youtube.com", "www.youtube.com")

        cmd = [
            "yt-dlp", url_or_search, "-x",
            "--audio-format", quality_cfg["format"],
            "--embed-metadata", "--no-playlist",
            "-o", str(Path(out_dir) / "%(title)s.%(ext)s")
        ]
        if quality_cfg["bitrate"]:
            cmd.extend(["--audio-quality", quality_cfg["bitrate"]])
        if quality_cfg["args"]:
            cmd.extend(quality_cfg["args"])

        subprocess.run(cmd, capture_output=True)

    def start_download_thread(self):
        self.download_btn.configure(state="disabled")
        thread = threading.Thread(target=self.process_download, daemon=True)
        thread.start()

    def process_download(self):
        link = self.link_entry.get().strip()
        if not link:
            messagebox.showwarning("Hiba", "Nincs megadva link!")
            self.download_btn.configure(state="normal")
            return

        quality = self.quality_map[self.quality_var.get()]
        save_path = Path(self.download_path.get())
        save_path.mkdir(parents=True, exist_ok=True)

        # Spotify ág
        if "spotify.com" in link:
            self.log("Spotify link elemzése...")
            sp = self.init_spotify()
            if not sp:
                self.log("HIBA: Spotify API kulcsok hiányoznak!")
            else:
                tracks = self.get_spotify_content(sp, link)
                if tracks:
                    self.log(f"{len(tracks)} szám feldolgozása...")
                    for i, track in enumerate(tracks, 1):
                        search = f"{track['artist']} - {track['title']}"
                        self.log(f"[{i}/{len(tracks)}] {search}")
                        self.download_audio(search, quality, save_path)
                    self.log("Letöltés befejezve!")

        # YouTube vagy keresés
        elif "youtube.com" in link or "youtu.be" in link:
            self.log("YouTube letöltés...")
            self.download_audio(link, quality, save_path)
            self.log("Kész!")
        else:
            self.log(f"Keresés és letöltés: {link}")
            self.download_audio(link, quality, save_path)
            self.log("Kész!")

        self.download_btn.configure(state="normal")
        messagebox.showinfo("Kész", "A művelet befejeződött!")

if __name__ == "__main__":
    app = MusicDownloaderGUI()
    app.mainloop()
