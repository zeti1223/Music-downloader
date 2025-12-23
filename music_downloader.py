import os
import subprocess
import threading
from pathlib import Path
import re
import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk
import datetime
import json

# .env fájl betöltése (SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)
from dotenv import load_dotenv
load_dotenv()

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class MusicDownloaderGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Music Downloader Pro")
        self.geometry("900x750")

        # Logika változók
        self.current_process = None
        self.stop_requested = False
        self.pause_requested = False
        self.download_queue = []
        self.is_downloading = False
        self.item_counter = 0

        # Konfiguráció
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
        self.tabview.grid(row=0, column=0, padx=15, pady=15, sticky="nsew")

        self.tab_queue = self.tabview.add("Queue & Download")
        self.tab_log = self.tabview.add("Detailed Log")
        self.tab_settings = self.tabview.add("Settings")

        self.setup_queue_tab()
        self.setup_log_tab()
        self.setup_settings_tab()

    def setup_queue_tab(self):
        # 1. sor: Link beviteli mező
        input_frame = ctk.CTkFrame(self.tab_queue, fg_color="transparent")
        input_frame.pack(fill="x", padx=10, pady=(10, 5))

        self.link_entry = ctk.CTkEntry(input_frame, placeholder_text="Spotify/YouTube link or search...", height=35)
        self.link_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        # 2. sor: Összes gomb egy sorban a helytakarékosság miatt
        controls_frame = ctk.CTkFrame(self.tab_queue, fg_color="transparent")
        controls_frame.pack(fill="x", padx=10, pady=5)

        self.add_btn = ctk.CTkButton(controls_frame, text="Add", width=70, command=self.add_to_queue_thread)
        self.add_btn.pack(side="left", padx=2)

        self.start_btn = ctk.CTkButton(controls_frame, text="Start All", fg_color="#1DB954", hover_color="#18a34a", width=90, command=self.start_downloads)
        self.start_btn.pack(side="left", padx=2)

        self.pause_btn = ctk.CTkButton(controls_frame, text="Pause", fg_color="#FF8C00", hover_color="#e67e00", width=90, command=self.toggle_pause)
        self.pause_btn.pack(side="left", padx=2)

        self.abort_btn = ctk.CTkButton(controls_frame, text="Abort", fg_color="#a31818", hover_color="#7a1212", width=90, command=self.abort_process)
        self.abort_btn.pack(side="left", padx=2)

        self.clear_btn = ctk.CTkButton(controls_frame, text="Clear List", fg_color="#444444", width=90, command=self.clear_queue_list)
        self.clear_btn.pack(side="left", padx=2)

        # Queue keret (kitölti a maradék helyet)
        self.queue_frame = ctk.CTkScrollableFrame(self.tab_queue)
        self.queue_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Statisztika sor alul
        self.speed_label = ctk.CTkLabel(self.tab_queue, text="Ready | Speed: 0 KiB/s | Progress: 0%", font=ctk.CTkFont(family="Consolas", size=12))
        self.speed_label.pack(pady=5)

    def setup_log_tab(self):
        self.full_log_text = ctk.CTkTextbox(self.tab_log, font=ctk.CTkFont(family="Consolas", size=11))
        self.full_log_text.pack(fill="both", expand=True, padx=10, pady=10)
        self.full_log_text.configure(state="disabled")

    def setup_settings_tab(self):
        ctk.CTkLabel(self.tab_settings, text="Download Root Folder:", font=ctk.CTkFont(weight="bold")).pack(pady=(20, 5))
        self.path_entry = ctk.CTkEntry(self.tab_settings, textvariable=self.download_path, width=500)
        self.path_entry.pack(pady=5)
        self.browse_btn = ctk.CTkButton(self.tab_settings, text="Browse", command=self.browse_folder)
        self.browse_btn.pack(pady=5)

        ctk.CTkLabel(self.tab_settings, text="Format & Quality:", font=ctk.CTkFont(weight="bold")).pack(pady=(30, 5))
        self.quality_dropdown = ctk.CTkOptionMenu(self.tab_settings, values=list(self.quality_map.keys()), variable=self.quality_var)
        self.quality_dropdown.pack(pady=10)

    # --- UI Helpers ---

    def log(self, message, level="INFO"):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        msg = f"[{ts}] [{level}] {message}\n"
        self.full_log_text.configure(state="normal")
        self.full_log_text.insert("end", msg)
        self.full_log_text.see("end")
        self.full_log_text.configure(state="disabled")

    def browse_folder(self):
        path = filedialog.askdirectory()
        if path: self.download_path.set(path)

    def refresh_queue_ui(self):
        for widget in self.queue_frame.winfo_children():
            widget.destroy()

        for index, item in enumerate(self.download_queue):
            row = ctk.CTkFrame(self.queue_frame, fg_color="transparent")
            row.pack(fill="x", pady=1)

            btn_up = ctk.CTkButton(row, text="▲", width=28, height=24, command=lambda i=index: self.move_item(i, -1))
            btn_up.pack(side="left", padx=1)
            btn_down = ctk.CTkButton(row, text="▼", width=28, height=24, command=lambda i=index: self.move_item(i, 1))
            btn_down.pack(side="left", padx=1)

            folder_info = f" [{item['folder']}]" if item['folder'] else ""
            status_colors = {"waiting": "white", "working": "#FF8C00", "done": "#1DB954", "error": "#FF0000"}

            lbl = ctk.CTkLabel(row, text=f"{item['display_name']}{folder_info}",
                               anchor="w", text_color=status_colors.get(item["status"], "white"), font=ctk.CTkFont(size=12))
            lbl.pack(side="left", padx=8, fill="x", expand=True)

    def move_item(self, index, direction):
        new_index = index + direction
        if 0 <= new_index < len(self.download_queue):
            self.download_queue[index], self.download_queue[new_index] = self.download_queue[new_index], self.download_queue[index]
            self.refresh_queue_ui()

    def toggle_pause(self):
        self.pause_requested = not self.pause_requested
        if self.pause_requested:
            self.pause_btn.configure(text="Resume", fg_color="#1f538d")
            self.log("Download PAUSED", "USER")
        else:
            self.pause_btn.configure(text="Pause", fg_color="#FF8C00")
            self.log("Download RESUMED", "USER")

    def abort_process(self):
        self.stop_requested = True
        if self.current_process:
            self.current_process.terminate()
        self.is_downloading = False
        self.speed_label.configure(text="Aborted | Speed: 0 KiB/s | Progress: 0%")
        self.log("Process ABORTED", "SYSTEM")

    def clear_queue_list(self):
        if self.is_downloading:
            messagebox.showwarning("Warning", "Stop downloading before clearing.")
            return
        self.download_queue.clear()
        self.refresh_queue_ui()
        self.speed_label.configure(text="Ready | Speed: 0 KiB/s | Progress: 0%")
        self.log("Queue list cleared", "UI")

    # --- Logic ---

    def init_spotify(self):
        cid, sec = os.getenv("SPOTIFY_CLIENT_ID"), os.getenv("SPOTIFY_CLIENT_SECRET")
        if not cid or not sec: return None
        return spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=cid, client_secret=sec))

    def add_to_queue_thread(self):
        link = self.link_entry.get().strip()
        if not link: return
        self.add_btn.configure(state="disabled")
        threading.Thread(target=self.process_input, args=(link,), daemon=True).start()
        self.link_entry.delete(0, 'end')

    def process_input(self, link):
        self.log(f"Analyzing: {link}", "ANALYZER")

        # SPOTIFY logic
        if "spotify.com" in link or "open.spotify.com" in link:
            sp = self.init_spotify()
            if not sp:
                self.log("Spotify keys missing!", "ERROR")
            else:
                try:
                    if "/playlist/" in link:
                        pl = sp.playlist(link)
                        f_name = re.sub(r'[\\/*?:"<>|]', "", pl['name'])
                        results = sp.playlist_items(link)
                        while results:
                            for item in results['items']:
                                if item.get('track'):
                                    t = item['track']
                                    name = f"{t['artists'][0]['name']} - {t['name']}"
                                    self.download_queue.append({"query": name, "display_name": name, "folder": f_name, "status": "waiting", "id": self.item_counter})
                                    self.item_counter += 1
                            results = sp.next(results) if results['next'] else None
                        self.log(f"Added Spotify Playlist: {pl['name']}", "SUCCESS")
                    elif "/track/" in link:
                        t = sp.track(link)
                        name = f"{t['artists'][0]['name']} - {t['name']}"
                        self.download_queue.append({"query": name, "display_name": name, "folder": None, "status": "waiting", "id": self.item_counter})
                        self.item_counter += 1
                except Exception as e: self.log(f"Spotify error: {e}", "ERROR")

        # YOUTUBE logic
        elif "youtube.com" in link or "youtu.be" in link:
            try:
                cmd = ["yt-dlp", "--flat-playlist", "--dump-single-json", link]
                res = subprocess.run(cmd, capture_output=True, text=True)
                data = json.loads(res.stdout)
                if 'entries' in data:
                    f_name = re.sub(r'[\\/*?:"<>|]', "", data['title'])
                    for entry in data['entries']:
                        title = entry.get('title', 'Unknown Title')
                        q = f"https://www.youtube.com/watch?v={entry['id']}" if 'id' in entry else title
                        self.download_queue.append({"query": q, "display_name": title, "folder": f_name, "status": "waiting", "id": self.item_counter})
                        self.item_counter += 1
                else:
                    title = data.get('title', link)
                    self.download_queue.append({"query": link, "display_name": title, "folder": None, "status": "waiting", "id": self.item_counter})
                    self.item_counter += 1
            except Exception as e: self.log(f"YT error: {e}", "ERROR")

        else: # Search fallback
            self.download_queue.append({"query": link, "display_name": link, "folder": None, "status": "waiting", "id": self.item_counter})
            self.item_counter += 1

        self.after(0, self.refresh_queue_ui)
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
            while self.pause_requested and not self.stop_requested:
                import time
                time.sleep(0.5)

            if self.stop_requested: break
            if item["status"] == "done": continue

            item["status"] = "working"
            self.after(0, self.refresh_queue_ui)

            save_dir = base_path / item['folder'] if item['folder'] else base_path
            save_dir.mkdir(parents=True, exist_ok=True)

            self.log(f"Downloading: {item['display_name']}", "DL")
            success = self.run_yt_dlp(item['query'], quality_cfg, save_dir)

            item["status"] = "done" if success else "error"
            self.log(f"{'Finished' if success else 'Failed'}: {item['display_name']}", "DL")
            self.after(0, self.refresh_queue_ui)

        self.is_downloading = False
        self.log("Batch process finished", "SYSTEM")

    def run_yt_dlp(self, query, cfg, out_dir):
        url = query if re.match(r'https?://', query) else f"ytsearch1:{query}"
        cmd = ["yt-dlp", url, "-x", "--audio-format", cfg["format"], "--newline", "-o", str(out_dir / "%(title)s.%(ext)s")]
        if cfg["bitrate"] and cfg["bitrate"] != "0": cmd.extend(["--audio-quality", cfg["bitrate"]])

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.current_process = proc

        for line in proc.stdout:
            if self.stop_requested: break
            self.log(line.strip(), "YTDLP")
            match = re.search(r'\[download\]\s+(\d+\.\d+)%.*at\s+([\d\.]+\w+/s)', line)
            if match:
                p, s = match.groups()
                self.after(0, lambda p=p, s=s: self.speed_label.configure(text=f"Speed: {s} | Progress: {p}%"))

        proc.wait()
        return proc.returncode == 0

if __name__ == "__main__":
    app = MusicDownloaderGUI()
    app.mainloop()
