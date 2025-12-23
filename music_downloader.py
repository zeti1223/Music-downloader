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

# Load .env file
load_dotenv()

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class MusicDownloaderGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Music Downloader Pro")
        self.geometry("800x750")

        # Core logic variables
        self.current_process = None
        self.stop_requested = False
        self.download_queue = []
        self.is_downloading = False

        # Configs
        self.download_path = tk.StringVar(value=str(Path.home() / "MusicDownloader"))
        self.quality_var = tk.StringVar(value="MP3 320kbps")

        self.quality_map = {
            "MP3 128kbps": {"format": "mp3", "bitrate": "128K", "args": []},
            "MP3 256kbps": {"format": "mp3", "bitrate": "256K", "args": []},
            "MP3 320kbps": {"format": "mp3", "bitrate": "320K", "args": []},
            "OGG": {"format": "vorbis", "bitrate": "192K", "args": []},
            "M4A": {"format": "m4a", "bitrate": "192K", "args": []},
            "MPEG": {"format": "mp3", "bitrate": "192K", "args": []},
            "FLAC": {"format": "flac", "bitrate": "0", "args": []},
        }

        self.setup_ui()

    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")

        self.tab_queue = self.tabview.add("Queue & Download")
        self.tab_settings = self.tabview.add("Settings")

        self.setup_queue_tab()
        self.setup_settings_tab()

    def setup_queue_tab(self):
        # Input Section
        input_frame = ctk.CTkFrame(self.tab_queue, fg_color="transparent")
        input_frame.pack(fill="x", padx=10, pady=10)

        self.link_entry = ctk.CTkEntry(input_frame, placeholder_text="Paste Spotify/YouTube link or search here...", width=450)
        self.link_entry.pack(side="left", padx=5)

        self.add_btn = ctk.CTkButton(input_frame, text="Add to Queue", command=self.add_to_queue_thread, width=120)
        self.add_btn.pack(side="left", padx=5)

        # Queue Listbox (using a textbox to simulate a list)
        ctk.CTkLabel(self.tab_queue, text="Download Queue:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=15)
        self.queue_display = ctk.CTkTextbox(self.tab_queue, height=300)
        self.queue_display.pack(fill="both", padx=10, pady=5)
        self.queue_display.configure(state="disabled")

        # Stats & Speed
        self.speed_label = ctk.CTkLabel(self.tab_queue, text="Speed: 0 KiB/s | Progress: 0%", font=ctk.CTkFont(family="Consolas"))
        self.speed_label.pack(pady=5)

        # Control Buttons
        btn_frame = ctk.CTkFrame(self.tab_queue, fg_color="transparent")
        btn_frame.pack(pady=10)

        self.start_btn = ctk.CTkButton(btn_frame, text="Start All", fg_color="#1DB954", command=self.start_downloads)
        self.start_btn.pack(side="left", padx=10)

        self.stop_btn = ctk.CTkButton(btn_frame, text="Stop / Clear", fg_color="#a31818", command=self.stop_download)
        self.stop_btn.pack(side="left", padx=10)

        # 3-Line Mini Log
        ctk.CTkLabel(self.tab_queue, text="Recent Activity:", font=ctk.CTkFont(size=11)).pack(anchor="w", padx=15)
        self.log_text = ctk.CTkTextbox(self.tab_queue, height=60, font=ctk.CTkFont(family="Consolas", size=11))
        self.log_text.pack(fill="x", padx=10, pady=5)
        self.log_text.configure(state="disabled")

    def setup_settings_tab(self):
        ctk.CTkLabel(self.tab_settings, text="Default Download Root:", font=ctk.CTkFont(weight="bold")).pack(pady=(20, 5))
        path_frame = ctk.CTkFrame(self.tab_settings, fg_color="transparent")
        path_frame.pack(fill="x", padx=40)
        self.path_entry = ctk.CTkEntry(path_frame, textvariable=self.download_path, width=350)
        self.path_entry.pack(side="left", padx=5)
        self.browse_btn = ctk.CTkButton(path_frame, text="Browse", width=80, command=self.browse_folder)
        self.browse_btn.pack(side="left")

        ctk.CTkLabel(self.tab_settings, text="Audio Format & Quality:", font=ctk.CTkFont(weight="bold")).pack(pady=(30, 5))
        self.quality_dropdown = ctk.CTkOptionMenu(self.tab_settings, values=list(self.quality_map.keys()), variable=self.quality_var)
        self.quality_dropdown.pack(pady=10)

    def browse_folder(self):
        path = filedialog.askdirectory()
        if path: self.download_path.set(path)

    def log(self, message):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"> {message}\n")
        # Keep only last 3 lines
        lines = self.log_text.get("1.0", "end").splitlines()
        if len(lines) > 4:
            self.log_text.delete("1.0", "2.0")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def update_queue_ui(self):
        self.queue_display.configure(state="normal")
        self.queue_display.delete("1.0", "end")
        for item in self.download_queue:
            folder_info = f" [Folder: {item['folder']}]" if item['folder'] else ""
            self.queue_display.insert("end", f"• {item['query']}{folder_info}\n")
        self.queue_display.configure(state="disabled")

    # --- Logic ---

    def init_spotify(self):
        cid = os.getenv("SPOTIFY_CLIENT_ID")
        secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        if not cid or not secret: return None
        return spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=cid, client_secret=secret))

    def add_to_queue_thread(self):
        link = self.link_entry.get().strip()
        if not link: return
        threading.Thread(target=self.process_input, args=(link,), daemon=True).start()
        self.link_entry.delete(0, 'end')

    def process_input(self, link):
        self.log("Analyzing input...")
        if "spotify.com" in link:
            sp = self.init_spotify()
            if not sp:
                self.log("Spotify API keys missing!")
                return

            try:
                if "/playlist/" in link:
                    pl = sp.playlist(link)
                    folder_name = re.sub(r'[\\/*?:"<>|]', "", pl['name'])
                    results = sp.playlist_items(link)
                    tracks = results['items']
                    while results['next']:
                        results = sp.next(results)
                        tracks.extend(results['items'])

                    for item in tracks:
                        if item.get('track'):
                            t = item['track']
                            self.download_queue.append({
                                "query": f"{t['artists'][0]['name']} - {t['name']}",
                                "folder": folder_name
                            })
                    self.log(f"Added playlist: {pl['name']}")
                elif "/track/" in link:
                    t = sp.track(link)
                    self.download_queue.append({"query": f"{t['artists'][0]['name']} - {t['name']}", "folder": None})
                    self.log("Added track to queue.")
            except Exception as e:
                self.log(f"Spotify Error: {e}")
        else:
            # YouTube or Search
            self.download_queue.append({"query": link, "folder": None})
            self.log("Added to queue.")

        self.after(0, self.update_queue_ui)

    def start_downloads(self):
        if not self.download_queue or self.is_downloading: return
        self.is_downloading = True
        self.stop_requested = False
        threading.Thread(target=self.download_loop, daemon=True).start()

    def download_loop(self):
        quality_cfg = self.quality_map[self.quality_var.get()]
        base_path = Path(self.download_path.get())

        while self.download_queue and not self.stop_requested:
            item = self.download_queue.pop(0)
            self.after(0, self.update_queue_ui)

            save_dir = base_path / item['folder'] if item['folder'] else base_path
            save_dir.mkdir(parents=True, exist_ok=True)

            self.log(f"Downloading: {item['query']}")
            self.run_yt_dlp(item['query'], quality_cfg, save_dir)

        self.is_downloading = False
        self.log("All tasks finished.")
        self.after(0, lambda: self.speed_label.configure(text="Speed: 0 KiB/s | Progress: 100%"))

    def run_yt_dlp(self, query, cfg, out_dir):
        url = query if re.match(r'https?://', query) else f"ytsearch1:{query}"

        cmd = [
            "yt-dlp", url, "-x",
            "--audio-format", cfg["format"],
            "--newline",
            "-o", str(out_dir / "%(title)s.%(ext)s")
        ]
        if cfg["bitrate"] and cfg["bitrate"] != "0":
            cmd.extend(["--audio-quality", cfg["bitrate"]])

        self.current_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

        for line in self.current_process.stdout:
            if self.stop_requested: break
            # Regex for speed and percentage
            match = re.search(r'\[download\]\s+(\d+\.\d+)%.*at\s+([\d\.]+\w+/s)', line)
            if match:
                percent, speed = match.groups()
                self.after(0, lambda p=percent, s=speed: self.speed_label.configure(text=f"Speed: {s} | Progress: {p}%"))

        self.current_process.wait()
        self.current_process = None

    def stop_download(self):
        self.stop_requested = True
        if self.current_process:
            self.current_process.terminate()
        self.download_queue.clear()
        self.update_queue_ui()
        self.log("Queue cleared & stopped.")

if __name__ == "__main__":
    app = MusicDownloaderGUI()
    app.mainloop()
