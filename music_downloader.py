import os
import subprocess
import threading
import json
import re
import datetime
import time
from pathlib import Path

# TUI imports
try:
    from textual.app import App, ComposeResult
    from textual.containers import Horizontal
    from textual.widgets import Header, Button, Input, Label, TabbedContent, TabPane, Log, DataTable, TextArea
except ImportError:
    print("Hiba: A 'textual' könyvtár hiányzik. Telepítsd: pip install textual")
    exit(1)

CONFIG_FILE = "config.json"

class VimDataTable(DataTable):
    BINDINGS = [
        ("up", "noop", ""),
        ("down", "noop", ""),
        ("left", "noop", ""),
        ("right", "noop", ""),
    ]
    def action_noop(self): pass
    def on_click(self, event): event.stop()
    def on_mouse_down(self, event): event.stop()
    def on_mouse_scroll_up(self, event): event.stop()
    def on_mouse_scroll_down(self, event): event.stop()

class MusicDownloaderApp(App):
    CSS = """
    Screen {
        layout: vertical;
    }
    DataTable {
        height: 1fr;
        border: solid $accent;
    }
    Log {
        height: 1fr;
        border: solid $accent;
    }
    .settings_field {
        margin-bottom: 1;
    }
    #cmd_line {
        dock: bottom;
        margin: 0;
        border-top: solid $accent;
    }
    Tabs {
        display: none;
    }
    """

    TITLE = "Music Downloader Pro (TUI)"
    BINDINGS = [
        (":", "focus_command", "Parancs mód"),
        ("j", "cursor_down", "Le"),
        ("k", "cursor_up", "Fel"),
    ]

    def __init__(self):
        super().__init__()

        # Logic variables
        self.current_process = None
        self.stop_requested = False
        self.pause_requested = False
        self.download_queue = []
        self.is_downloading = False
        self.item_counter = 0

        # Configuration variables
        self.cfg_path = str(Path.home() / "MusicDownloader")
        self.cfg_sp_id = ""
        self.cfg_sp_sec = ""
        self.cfg_quality = "MP3 320kbps"

        self.quality_map = {
            "MP3 128kbps": {"format": "mp3", "bitrate": "128K"},
            "MP3 256kbps": {"format": "mp3", "bitrate": "256K"},
            "MP3 320kbps": {"format": "mp3", "bitrate": "320K"},
            "WebM (Best Audio)": {"format": "webm", "bitrate": "0"},
            "OGG": {"format": "vorbis", "bitrate": "192K"},
            "M4A": {"format": "m4a", "bitrate": "192K"},
            "FLAC": {"format": "flac", "bitrate": "0"},
        }

        self.load_settings()

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("Queue & Download", id="tab_queue"):
                yield Label("Ready | Speed: 0 KiB/s | Progress: 0%", id="speed_label")
                yield VimDataTable(id="queue_table")

            with TabPane("Detailed Log", id="tab_log"):
                yield Log(id="full_log")

            with TabPane("Settings", id="tab_settings"):
                yield TextArea(id="settings_editor", language="properties")
        
        yield Input(placeholder="Parancsokhoz írd be: :help", id="cmd_line")

    def on_mount(self):
        table = self.query_one(DataTable)
        table.add_columns("ID", "Status", "Name", "Folder")
        table.focus()
        self.log_msg("Application started.", "SYSTEM")
        # Load settings into the editor
        self.update_settings_editor()

    def action_focus_command(self):
        cmd = self.query_one("#cmd_line", Input)
        cmd.value = ":"
        cmd.focus()
        cmd.cursor_position = len(cmd.value)

    def action_cursor_down(self):
        try: self.query_one(DataTable).action_cursor_down()
        except: pass

    def action_cursor_up(self):
        try: self.query_one(DataTable).action_cursor_up()
        except: pass

    def on_input_submitted(self, event: Input.Submitted):
        if event.input.id == "cmd_line":
            self.handle_command(event.value)
            event.input.value = ""
            event.input.blur()
            if self.query_one(TabbedContent).active == "tab_queue":
                self.query_one(DataTable).focus()

    def handle_command(self, cmd_str):
        cmd_str = cmd_str.strip()
        if not cmd_str.startswith(":"): return
        
        parts = cmd_str[1:].split(" ", 1)
        cmd = parts[0]
        args = parts[1] if len(parts) > 1 else ""

        if cmd in ["q", "quit"]:
            self.exit()
        elif cmd == "add":
            if args:
                threading.Thread(target=self.process_input, args=(args,), daemon=True).start()
            else:
                self.log_msg("Használat: :add <link>", "ERROR")
        elif cmd == "start":
            self.start_downloads()
        elif cmd == "pause":
            self.toggle_pause()
        elif cmd == "abort":
            self.abort_process()
        elif cmd == "clear":
            self.clear_queue_list()
        elif cmd == "save":
            self.save_settings()
        elif cmd == "queue":
            self.query_one(TabbedContent).active = "tab_queue"
        elif cmd == "log":
            self.query_one(TabbedContent).active = "tab_log"
        elif cmd == "settings":
            self.query_one(TabbedContent).active = "tab_settings"
        elif cmd == "help":
            self.log_msg("Parancsok: :add, :start, :pause, :abort, :clear, :save, :quit", "HELP")
            self.query_one(TabbedContent).active = "tab_log"
        else:
            self.log_msg(f"Ismeretlen parancs: {cmd}", "ERROR")

    def load_settings(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    self.cfg_path = data.get("path", self.cfg_path)
                    self.cfg_sp_id = data.get("sp_id", "")
                    self.cfg_sp_sec = data.get("sp_sec", "")
                    self.cfg_quality = data.get("quality", "MP3 320kbps")
            except: pass

    def update_settings_editor(self):
        # Convert internal quality to short code
        q_code = "mp3-3"
        if "128" in self.cfg_quality: q_code = "mp3-1"
        elif "256" in self.cfg_quality: q_code = "mp3-2"
        elif "320" in self.cfg_quality: q_code = "mp3-3"
        elif "WebM" in self.cfg_quality: q_code = "webm"
        elif "OGG" in self.cfg_quality: q_code = "ogg"
        elif "M4A" in self.cfg_quality: q_code = "m4a"
        elif "FLAC" in self.cfg_quality: q_code = "flac"

        text = (
            f"path={self.cfg_path}\n"
            f"sp_id={self.cfg_sp_id}\n"
            f"sp_sec={self.cfg_sp_sec}\n"
            f"quality={q_code}\n"
        )
        try:
            self.query_one("#settings_editor", TextArea).text = text
        except: pass

    def save_settings(self):
        # Parse settings from TextArea
        raw_text = self.query_one("#settings_editor", TextArea).text
        new_conf = {}
        for line in raw_text.splitlines():
            if "=" in line:
                key, val = line.split("=", 1)
                new_conf[key.strip()] = val.strip()

        self.cfg_path = new_conf.get("path", self.cfg_path)
        self.cfg_sp_id = new_conf.get("sp_id", self.cfg_sp_id)
        self.cfg_sp_sec = new_conf.get("sp_sec", self.cfg_sp_sec)
        
        q_input = new_conf.get("quality", "mp3-3").lower()
        if q_input == "mp3-1": self.cfg_quality = "MP3 128kbps"
        elif q_input == "mp3-2": self.cfg_quality = "MP3 256kbps"
        elif q_input == "mp3-3": self.cfg_quality = "MP3 320kbps"
        elif q_input == "webm": self.cfg_quality = "WebM (Best Audio)"
        elif q_input == "ogg": self.cfg_quality = "OGG"
        elif q_input == "m4a": self.cfg_quality = "M4A"
        elif q_input == "flac": self.cfg_quality = "FLAC"

        data = {
            "path": self.cfg_path,
            "sp_id": self.cfg_sp_id,
            "sp_sec": self.cfg_sp_sec,
            "quality": self.cfg_quality
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f)
        self.log_msg("Settings saved to local config.", "UI")
        self.log_msg("Configuration saved!", "SYSTEM")

    def log_msg(self, message, level="INFO"):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        msg = f"[{ts}] [{level}] {message}\n"
        if threading.get_ident() == self._thread_id:
            self.query_one("#full_log", Log).write(msg)
        else:
            self.call_from_thread(self.query_one("#full_log", Log).write, msg)

    def refresh_queue_ui(self):
        if threading.get_ident() == self._thread_id:
            self._refresh_table()
        else:
            self.call_from_thread(self._refresh_table)

    def _refresh_table(self):
        table = self.query_one(DataTable)
        table.clear()
        for item in self.download_queue:
            folder_str = item['folder'] if item['folder'] else "-"
            table.add_row(str(item['id']), item['status'].upper(), item['display_name'], folder_str)

    def toggle_pause(self):
        self.pause_requested = not self.pause_requested
        self.log_msg(f"Process {'PAUSED' if self.pause_requested else 'RESUMED'}", "USER")

    def abort_process(self):
        self.stop_requested = True
        if self.current_process: self.current_process.terminate()
        self.is_downloading = False
        self.query_one("#speed_label", Label).update("Aborted | Speed: 0 KiB/s | Progress: 0%")
        self.log_msg("Download process aborted.", "SYSTEM")

    def clear_queue_list(self):
        if self.is_downloading: return
        self.download_queue.clear()
        self.refresh_queue_ui()
        self.query_one("#speed_label", Label).update("Ready | Speed: 0 KiB/s | Progress: 0%")
        self.log_msg("Queue cleared.", "UI")

    def init_spotify(self):
        cid = self.cfg_sp_id
        sec = self.cfg_sp_sec
        if not cid or not sec:
            self.log_msg("ERROR: Missing Spotify ID or Secret in Settings!", "ERROR")
            return None
        try:
            import spotipy
            from spotipy.oauth2 import SpotifyClientCredentials
            return spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=cid, client_secret=sec))
        except Exception as e:
            self.log_msg(f"Spotify Authentication Failed: {e}", "ERROR")
            return None

    def process_input(self, link):
        self.log_msg(f"Analyzing: {link}", "ANALYZER")
        clean_link = link.split('?')[0]

        # Spotify detection
        if "spotify.com" in clean_link:
            sp = self.init_spotify()
            if not sp:
                return

            try:
                if "/playlist/" in clean_link:
                    playlist_id = clean_link.split("/playlist/")[1].split("/")[0]
                    pl = sp.playlist(playlist_id)
                    f_name = re.sub(r'[\\/*?:"<>|]', "", pl['name'])
                    results = sp.playlist_items(playlist_id)
                    tracks = results['items']
                    while results['next']:
                        results = sp.next(results)
                        tracks.extend(results['items'])

                    for item in tracks:
                        if item.get('track'):
                            t = item['track']
                            name = f"{t['artists'][0]['name']} - {t['name']}"
                            self.download_queue.append({"query": name, "display_name": name, "folder": f_name, "status": "waiting", "id": self.item_counter})
                            self.item_counter += 1
                    self.log_msg(f"Added {len(tracks)} tracks from playlist: {pl['name']}", "SUCCESS")

                elif "/track/" in clean_link:
                    track_id = clean_link.split("/track/")[1].split("/")[0]
                    t = sp.track(track_id)
                    name = f"{t['artists'][0]['name']} - {t['name']}"
                    self.download_queue.append({"query": name, "display_name": name, "folder": None, "status": "waiting", "id": self.item_counter})
                    self.item_counter += 1
                    self.log_msg(f"Added track: {name}", "SUCCESS")
            except Exception as e:
                self.log_msg(f"Spotify API error: {e}", "ERROR")

        elif "youtube.com" in link or "youtu.be" in link:
            try:
                cmd = ["yt-dlp", "--flat-playlist", "--dump-single-json", link]
                res = subprocess.run(cmd, capture_output=True, text=True)
                data = json.loads(res.stdout)
                if 'entries' in data:
                    f_name = re.sub(r'[\\/*?:"<>|]', "", data.get('title', 'YT_Playlist'))
                    for entry in data['entries']:
                        title = entry.get('title', 'Unknown Title')
                        url = f"https://www.youtube.com/watch?v={entry['id']}" if 'id' in entry else title
                        self.download_queue.append({"query": url, "display_name": title, "folder": f_name, "status": "waiting", "id": self.item_counter})
                        self.item_counter += 1
                    self.log_msg(f"Added YouTube playlist: {f_name}", "SUCCESS")
                else:
                    title = data.get('title', link)
                    self.download_queue.append({"query": link, "display_name": title, "folder": None, "status": "waiting", "id": self.item_counter})
                    self.item_counter += 1
                    self.log_msg(f"Added YouTube video: {title}", "SUCCESS")
            except Exception as e: self.log_msg(f"YouTube analyzer error: {e}", "ERROR")

        else: # Generic search
            self.download_queue.append({"query": link, "display_name": link, "folder": None, "status": "waiting", "id": self.item_counter})
            self.item_counter += 1
            self.log_msg(f"Added search query: {link}", "SUCCESS")

        self.refresh_queue_ui()

    def start_downloads(self):
        if not self.download_queue or self.is_downloading: return
        self.is_downloading = True
        self.stop_requested = False
        # Run download loop in a thread to not block TUI
        threading.Thread(target=self.download_loop, daemon=True).start() 

    def download_loop(self):
        quality_cfg = self.quality_map[self.cfg_quality]
        base_path = Path(self.cfg_path)

        for item in self.download_queue:
            while self.pause_requested and not self.stop_requested:
                time.sleep(0.5)

            if self.stop_requested: break
            if item["status"] == "done": continue

            item["status"] = "working"
            self.refresh_queue_ui()

            save_dir = base_path / item['folder'] if item['folder'] else base_path
            save_dir.mkdir(parents=True, exist_ok=True)

            self.log_msg(f"Downloading: {item['display_name']}", "PROCESS")
            success = self.run_yt_dlp(item['query'], quality_cfg, save_dir)

            item["status"] = "done" if success else "error"
            self.refresh_queue_ui()

        self.is_downloading = False
        self.log_msg("All tasks completed.", "SYSTEM")

    def run_yt_dlp(self, query, cfg, out_dir):
        url = query if query.startswith("http") else f"ytsearch1:{query}"

        # Base command
        cmd = ["yt-dlp", url, "-x", "--audio-format", cfg["format"], "--newline", "-o", str(out_dir / "%(title)s.%(ext)s")]

        # WebM handling - usually we want the best audio without recoding if possible
        if cfg["format"] == "webm":
            # Just extract best audio that is webm/opus
            cmd = ["yt-dlp", url, "-f", "bestaudio[ext=webm]/bestaudio", "--newline", "-o", str(out_dir / "%(title)s.%(ext)s")]
        elif cfg["bitrate"] != "0":
            cmd.extend(["--audio-quality", cfg["bitrate"]])

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.current_process = proc
        for line in proc.stdout:
            if self.stop_requested: break
            match = re.search(r'\[download\]\s+(\d+\.\d+)%.*at\s+([\d\.]+\w+/s)', line)
            if match:
                p, s = match.groups()
                self.call_from_thread(self.query_one("#speed_label", Label).update, f"Speed: {s} | Progress: {p}%")
        proc.wait()
        return proc.returncode == 0

if __name__ == "__main__":
    app = MusicDownloaderApp()
    app.run()
