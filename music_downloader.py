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
import json

# Load .env file
load_dotenv()

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class MusicDownloaderGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Music Downloader Pro")
        self.geometry("900x800")

        # Core logic variables
        self.current_process = None
        self.stop_requested = False
        self.download_queue = []
        self.queue_widgets = {}  # Store labels for color updates
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
        self.tab_log = self.tabview.add("Full Log")
        self.tab_settings = self.tabview.add("Settings")

        self.setup_queue_tab()
        self.setup_log_tab()
        self.setup_settings_tab()

    def setup_queue_tab(self):
        # Input Section
        input_frame = ctk.CTkFrame(self.tab_queue, fg_color="transparent")
        input_frame.pack(fill="x", padx=10, pady=10)

        self.link_entry = ctk.CTkEntry(input_frame, placeholder_text="Paste Spotify/YouTube link or search here...", width=550)
        self.link_entry.pack(side="left", padx=5)

        self.add_btn = ctk.CTkButton(input_frame, text="Add to Queue", command=self.add_to_queue_thread, width=120)
        self.add_btn.pack(side="left", padx=5)

        # Queue List (Scrollable Frame for individual coloring)
        ctk.CTkLabel(self.tab_queue, text="Download Queue:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=15)
        self.queue_frame = ctk.CTkScrollableFrame(self.tab_queue, height=350)
        self.queue_frame.pack(fill="both", padx=10, pady=5)

        # Stats & Speed
        self.speed_label = ctk.CTkLabel(self.tab_queue, text="Speed: 0 KiB/s | Progress: 0%", font=ctk.CTkFont(family="Consolas"))
        self.speed_label.pack(pady=5)

        # Control Buttons
        btn_frame = ctk.CTkFrame(self.tab_queue, fg_color="transparent")
        btn_frame.pack(pady=10)

        self.start_btn = ctk.CTkButton(btn_frame, text="Start All", fg_color="#1DB954", command=self.start_downloads)
        self.start_btn.pack(side="left", padx=10)

        self.stop_btn = ctk.CTkButton(btn_frame, text="Clear / Stop", fg_color="#a31818", command=self.clear_queue)
        self.stop_btn.pack(side="left", padx=10)

    def setup_log_tab(self):
        self.full_log_text = ctk.CTkTextbox(self.tab_log, font=ctk.CTkFont(family="Consolas", size=12))
        self.full_log_text.pack(fill="both", expand=True, padx=10, pady=10)
        self.full_log_text.configure(state="disabled")

    def setup_settings_tab(self):
        ctk.CTkLabel(self.tab_settings, text="Default Download Root:", font=ctk.CTkFont(weight="bold")).pack(pady=(20, 5))
        path_frame = ctk.CTkFrame(self.tab_settings, fg_color="transparent")
        path_frame.pack(fill="x", padx=40)
        self.path_entry = ctk.CTkEntry(path_frame, textvariable=self.download_path, width=450)
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
        self.full_log_text.configure(state="normal")
        self.full_log_text.insert("end", f"> {message}\n")
        self.full_log_text.see("end")
        self.full_log_text.configure(state="disabled")

    def add_to_queue_ui(self, item_id, text, folder):
        folder_info = f" (Folder: {folder})" if folder else ""
        lbl = ctk.CTkLabel(self.queue_frame, text=f"• {text}{folder_info}", anchor="w", font=ctk.CTkFont(size=12))
        lbl.pack(fill="x", padx=5, pady=2)
        self.queue_widgets[item_id] = lbl

    def update_item_status(self, item_id, status):
        # status: "waiting" (default), "working" (orange), "done" (green), "error" (red)
        colors = {"waiting": "white", "working": "#FF8C00", "done": "#1DB954", "error": "#FF0000"}
        if item_id in self.queue_widgets:
            self.queue_widgets[item_id].configure(text_color=colors.get(status, "white"))

    # --- Logic ---

    def init_spotify(self):
        cid = os.getenv("SPOTIFY_CLIENT_ID")
        secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        if not cid or not secret: return None
        return spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=cid, client_secret=secret))

    def add_to_queue_thread(self):
        link = self.link_entry.get().strip()
        if not link: return
        self.add_btn.configure(state="disabled")
        threading.Thread(target=self.process_input, args=(link,), daemon=True).start()
        self.link_entry.delete(0, 'end')

    def process_input(self, link):
        self.log(f"Analyzing: {link}")

        # SPOTIFY
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
                            title = f"{t['artists'][0]['name']} - {t['name']}"
                            item_id = len(self.download_queue)
                            self.download_queue.append({"query": title, "folder": folder_name, "status": "waiting", "id": item_id})
                            self.after(0, lambda i=item_id, t=title, f=folder_name: self.add_to_queue_ui(i, t, f))
                elif "/track/" in link:
                    t = sp.track(link)
                    title = f"{t['artists'][0]['name']} - {t['name']}"
                    item_id = len(self.download_queue)
                    self.download_queue.append({"query": title, "folder": None, "status": "waiting", "id": item_id})
                    self.after(0, lambda i=item_id, t=title: self.add_to_queue_ui(i, t, None))
            except Exception as e:
                self.log(f"Spotify Error: {e}")

        # YOUTUBE / YT MUSIC
        elif "youtube.com" in link or "youtu.be" in link:
            try:
                # Get info using yt-dlp to see if it's a playlist or single video
                cmd = ["yt-dlp", "--flat-playlist", "--dump-single-json", link]
                result = subprocess.run(cmd, capture_output=True, text=True)
                data = json.loads(result.stdout)

                if 'entries' in data: # It's a playlist
                    folder_name = re.sub(r'[\\/*?:"<>|]', "", data['title'])
                    for entry in data['entries']:
                        title = entry['title']
                        item_id = len(self.download_queue)
                        # We use the original URL or search for the title
                        query = f"https://www.youtube.com/watch?v={entry['id']}" if 'id' in entry else title
                        self.download_queue.append({"query": query, "folder": folder_name, "status": "waiting", "id": item_id, "display_name": title})
                        self.after(0, lambda i=item_id, t=title, f=folder_name: self.add_to_queue_ui(i, t, f))
                else: # Single video
                    title = data['title']
                    item_id = len(self.download_queue)
                    self.download_queue.append({"query": link, "folder": None, "status": "waiting", "id": item_id, "display_name": title})
                    self.after(0, lambda i=item_id, t=title: self.add_to_queue_ui(i, t, None))
            except Exception as e:
                self.log(f"YouTube analyzer error: {e}")
                # Fallback: just add the raw link
                item_id = len(self.download_queue)
                self.download_queue.append({"query": link, "folder": None, "status": "waiting", "id": item_id})
                self.after(0, lambda i=item_id: self.add_to_queue_ui(i, link, None))

        else:
            # Simple Search
            item_id = len(self.download_queue)
            self.download_queue.append({"query": link, "folder": None, "status": "waiting", "id": item_id})
            self.after(0, lambda i=item_id: self.add_to_queue_ui(i, link, None))

        self.after(0, lambda: self.add_btn.configure(state="normal"))

    def start_downloads(self):
        if not self.download_queue or self.is_downloading: return
        self.is_downloading = True
        self.stop_requested = False
        threading.Thread(target=self.download_loop, daemon=True).start()

    def download_loop(self):
        quality_cfg = self.quality_map[self.quality_var.get()]
        base_path = Path(self.download_path.get())

        for item in self.download_queue:
            if self.stop_requested: break
            if item["status"] == "done": continue

            item["status"] = "working"
            self.after(0, lambda i=item["id"]: self.update_item_status(i, "working"))

            save_dir = base_path / item['folder'] if item['folder'] else base_path
            save_dir.mkdir(parents=True, exist_ok=True)

            display = item.get("display_name", item["query"])
            self.log(f"Starting: {display}")

            success = self.run_yt_dlp(item['query'], quality_cfg, save_dir)

            if success:
                item["status"] = "done"
                self.after(0, lambda i=item["id"]: self.update_item_status(i, "done"))
            else:
                item["status"] = "error"
                self.after(0, lambda i=item["id"]: self.update_item_status(i, "error"))

        self.is_downloading = False
        self.log("Batch process finished.")

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

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.current_process = process

        for line in process.stdout:
            if self.stop_requested: break
            match = re.search(r'\[download\]\s+(\d+\.\d+)%.*at\s+([\d\.]+\w+/s)', line)
            if match:
                percent, speed = match.groups()
                self.after(0, lambda p=percent, s=speed: self.speed_label.configure(text=f"Speed: {s} | Progress: {p}%"))

        process.wait()
        return process.returncode == 0

    def clear_queue(self):
        self.stop_requested = True
        if self.current_process:
            self.current_process.terminate()

        for widget in self.queue_frame.winfo_children():
            widget.destroy()

        self.download_queue.clear()
        self.queue_widgets.clear()
        self.log("Queue cleared.")

if __name__ == "__main__":
    app = MusicDownloaderGUI()
    app.mainloop()
