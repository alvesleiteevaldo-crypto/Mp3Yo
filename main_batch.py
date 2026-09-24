"""Interface opcional para converter até 30 links em sequência.

O aplicativo original permanece em main.py, sem modificações.
"""

import json
import os
from pathlib import Path
import shutil
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from urllib.parse import urlparse

import yt_dlp


FORMATS = ("mp3", "m4a", "opus", "flac", "wav")
MAX_LINKS = 30
BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
CONFIG_DIR = Path(os.environ.get("APPDATA", Path.home())) / "YoutuberAudioDownloader"
CONFIG = CONFIG_DIR / "config.json"


def valid_url(value):
    try:
        parsed = urlparse(value.strip())
        host = (parsed.hostname or "").lower()
        return parsed.scheme in ("http", "https") and host in (
            "youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com",
            "youtu.be", "www.youtu.be",
        ) and bool(parsed.path.strip("/"))
    except ValueError:
        return False


def ffmpeg_location():
    name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    local = BASE / "bin" / name
    if local.is_file():
        return str(local)
    found = shutil.which(name)
    if found:
        return found
    raise FileNotFoundError(f"FFmpeg não encontrado. Instale-o ou coloque {name} em bin/.")


def options_for(folder, audio_format, progress_hook):
    return {
        "format": "bestaudio/best",
        "noplaylist": True,
        "outtmpl": str(Path(folder) / "%(title).180B [%(id)s].%(ext)s"),
        "ffmpeg_location": ffmpeg_location(),
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": audio_format,
            "preferredquality": "192" if audio_format == "mp3" else "0",
        }],
        "progress_hooks": [progress_hook],
        "quiet": True,
        "no_warnings": True,
    }


class App:
    def __init__(self, root):
        self.root = root
        self.running = False
        root.title("YouTube Audio Downloader — fila de até 30 links")
        root.geometry("760x650")
        root.configure(bg="#333333")
        frame = tk.Frame(root, bg="#333333", padx=20, pady=15)
        frame.pack(fill="both", expand=True)

        def label(text):
            tk.Label(frame, text=text, bg="#333333", fg="white", anchor="w").pack(fill="x")

        label("Links do YouTube (um por linha; máximo de 30):")
        self.links = tk.Text(frame, height=17, wrap="none")
        self.links.pack(fill="both", expand=True, pady=(5, 12))
        row = tk.Frame(frame, bg="#333333")
        row.pack(fill="x")
        tk.Label(row, text="Formato de saída:", bg="#333333", fg="white").pack(side="left")
        self.audio_format = tk.StringVar(value="mp3")
        ttk.Combobox(row, textvariable=self.audio_format, values=FORMATS,
                     state="readonly", width=10).pack(side="left", padx=10)
        label("Pasta de destino:")
        folder_row = tk.Frame(frame, bg="#333333")
        folder_row.pack(fill="x", pady=(5, 12))
        self.folder = tk.StringVar(value=self.load_folder())
        tk.Entry(folder_row, textvariable=self.folder).pack(side="left", fill="x", expand=True)
        tk.Button(folder_row, text="Selecionar", command=self.select_folder).pack(side="left", padx=8)
        self.start_button = tk.Button(frame, text="Converter links em sequência", bg="#006600",
                                      fg="white", command=self.start)
        self.start_button.pack(fill="x", pady=(0, 10))
        self.progress = ttk.Progressbar(frame, maximum=100)
        self.progress.pack(fill="x")
        self.status = tk.StringVar(value="Aguardando...")
        label_status = tk.Label(frame, textvariable=self.status, bg="#333333", fg="white",
                                anchor="w", wraplength=700)
        label_status.pack(fill="x", pady=8)
        self.log = tk.Text(frame, height=6, state="disabled", wrap="word")
        self.log.pack(fill="both")

    @staticmethod
    def load_folder():
        try:
            return json.loads(CONFIG.read_text(encoding="utf-8")).get("destination_folder", "")
        except (FileNotFoundError, OSError, ValueError):
            return ""

    def select_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.folder.set(folder)

    def report(self, line):
        self.log.config(state="normal")
        self.log.insert("end", line + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def start(self):
        if self.running:
            return
        urls = [line.strip() for line in self.links.get("1.0", "end").splitlines() if line.strip()]
        folder = self.folder.get().strip()
        if not 1 <= len(urls) <= MAX_LINKS:
            messagebox.showwarning("Links", "Informe entre 1 e 30 links, um por linha.")
            return
        bad = [str(i) for i, url in enumerate(urls, 1) if not valid_url(url)]
        if bad:
            messagebox.showwarning("Links", "Link inválido nas linhas: " + ", ".join(bad))
            return
        if self.audio_format.get() not in FORMATS:
            messagebox.showwarning("Formato", "Selecione um formato de áudio válido.")
            return
        if not os.path.isdir(folder):
            messagebox.showwarning("Pasta", "Selecione uma pasta de destino existente.")
            return
        try:
            binary = ffmpeg_location()
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            CONFIG.write_text(json.dumps({"destination_folder": folder}), encoding="utf-8")
        except (OSError, FileNotFoundError) as exc:
            messagebox.showerror("Preparação", str(exc))
            return
        self.running = True
        self.start_button.config(state="disabled")
        self.progress.configure(value=0)
        self.report(f"Iniciando {len(urls)} link(s) em {self.audio_format.get().upper()}.")
        threading.Thread(target=self.worker,
                         args=(urls, folder, self.audio_format.get(), binary), daemon=True).start()

    def worker(self, urls, folder, audio_format, binary):
        successes = 0
        failures = 0
        for index, url in enumerate(urls, 1):
            self.root.after(0, lambda n=index: (self.progress.configure(value=0),
                           self.status.set(f"Processando {n}/{len(urls)}: {urls[n-1]}")))

            def hook(data, n=index):
                if data.get("status") == "downloading":
                    total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
                    percent = min(100, 100 * data.get("downloaded_bytes", 0) / total) if total else 0
                    self.root.after(0, lambda p=percent: self.progress.configure(value=p))
                elif data.get("status") == "finished":
                    self.root.after(0, lambda: self.status.set(
                        f"{n}/{len(urls)}: convertendo para {audio_format.upper()}..."))

            try:
                opts = options_for(folder, audio_format, hook)
                opts["ffmpeg_location"] = binary
                with yt_dlp.YoutubeDL(opts) as downloader:
                    downloader.download([url])
                successes += 1
                self.root.after(0, lambda n=index: self.report(f"{n}/{len(urls)}: concluído."))
            except Exception as exc:
                failures += 1
                error = str(exc)
                self.root.after(0, lambda n=index, e=error: self.report(f"{n}/{len(urls)}: erro: {e}"))
        self.root.after(0, lambda: self.finish(successes, failures))

    def finish(self, successes, failures):
        self.running = False
        self.start_button.config(state="normal")
        self.status.set(f"Fila concluída: {successes} sucesso(s), {failures} falha(s).")
        messagebox.showinfo("Resultado", self.status.get())


if __name__ == "__main__":
    App(tk.Tk()).root.mainloop()
