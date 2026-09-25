"""Interface para YouTube e TikTok; a extração anterior permanece intacta.

O aplicativo original permanece em main.py, sem modificações.
"""

import json
import os
import re
from pathlib import Path
import shutil
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from urllib.parse import urlparse, parse_qs

import yt_dlp


FORMATS = ("mp3", "m4a", "opus", "flac", "wav")
MP3_QUALITIES = ("192", "256", "320")
MAX_LINKS = 100
BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
CONFIG_DIR = Path(os.environ.get("APPDATA", Path.home())) / "YoutuberAudioDownloader"
CONFIG = CONFIG_DIR / "config.json"


def valid_url(value):
    try:
        parsed = urlparse(value.strip())
        host = (parsed.hostname or "").lower()
        youtube = host in (
            "youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com",
            "youtu.be", "www.youtu.be",
        ) and bool(parsed.path.strip("/"))
        tiktok = host in ("tiktok.com", "www.tiktok.com", "m.tiktok.com",
                          "vm.tiktok.com", "vt.tiktok.com") and (
            (host in ("vm.tiktok.com", "vt.tiktok.com") and bool(parsed.path.strip("/")))
            or ("video" in parsed.path.split("/") and bool(parsed.path.rstrip("/").split("/")[-1]))
        )
        return parsed.scheme in ("http", "https") and (youtube or tiktok)
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


def youtube_links(text):
    candidates = re.findall(r"https?://[^\s<>\"']+", text)
    return [url for candidate in candidates
            if valid_url(url := candidate.rstrip(".,;)]}"))]


def link_key(url):
    """Identifica o mesmo vídeo mesmo com domínio curto ou parâmetros extras."""
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower()
    parts = parsed.path.strip("/").split("/")
    if host.endswith("tiktok.com"):
        if "video" in parts:
            video_index = parts.index("video")
            if len(parts) > video_index + 1:
                return "tiktok:" + parts[video_index+1]
        return "tiktok-short:" + host + "/" + parsed.path.strip("/")
    if host in ("youtu.be", "www.youtu.be"):
        video_id = parts[0]
    elif parts[0] == "watch":
        video_id = parse_qs(parsed.query).get("v", [""])[0]
    elif parts[0] in ("shorts", "live", "embed") and len(parts) > 1:
        video_id = parts[1]
    else:
        video_id = ""
    return "video:" + video_id if video_id else url.strip()


def unique_links(urls):
    seen, result = set(), []
    for url in urls:
        key = link_key(url)
        if key not in seen:
            seen.add(key)
            result.append(url)
    return result


def options_for(folder, audio_format, progress_hook, mp3_quality="192"):
    return {
        "format": "bestaudio/best",
        "noplaylist": True,
        "outtmpl": str(Path(folder) / "%(title).180B [%(id)s].%(ext)s"),
        "ffmpeg_location": ffmpeg_location(),
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": audio_format,
            "preferredquality": mp3_quality if audio_format == "mp3" else "0",
        }],
        "progress_hooks": [progress_hook],
        "quiet": True,
        "no_warnings": True,
    }


class App:
    def __init__(self, root):
        self.root = root
        self.running = False
        root.title("Converte MP3 Sem Limite Evaldo — YouTube e TikTok")
        root.geometry("820x850")
        root.configure(bg="#333333")
        frame = tk.Frame(root, bg="#333333", padx=20, pady=15)
        frame.pack(fill="both", expand=True)

        def label(text):
            tk.Label(frame, text=text, bg="#333333", fg="white", anchor="w").pack(fill="x")

        label("Links do YouTube ou TikTok (um por linha; até 100, sem repetição):")
        self.links = tk.Text(frame, height=10, wrap="none")
        self.links.pack(fill="both", expand=True, pady=(5, 12))
        self.auto_clipboard = tk.BooleanVar(value=True)
        tk.Checkbutton(frame, text="Adicionar links copiados do YouTube ou TikTok (sem iniciar download)",
                       variable=self.auto_clipboard, bg="#333333", fg="white",
                       selectcolor="#333333", activebackground="#333333",
                       activeforeground="white").pack(anchor="w", pady=(0, 8))
        self.last_clipboard = None
        label("Progresso por link:")
        table_frame = tk.Frame(frame)
        table_frame.pack(fill="both", expand=True, pady=(3, 8))
        self.table = ttk.Treeview(table_frame, columns=("link", "progress", "status"),
                                  show="headings", height=9)
        self.table.heading("link", text="Link")
        self.table.heading("progress", text="Progresso")
        self.table.heading("status", text="Resultado")
        self.table.column("link", width=530, stretch=True)
        self.table.column("progress", width=85, stretch=False, anchor="center")
        self.table.column("status", width=100, stretch=False, anchor="center")
        self.table.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(table_frame, command=self.table.yview)
        scrollbar.pack(side="right", fill="y")
        self.table.configure(yscrollcommand=scrollbar.set)
        row = tk.Frame(frame, bg="#333333")
        row.pack(fill="x")
        tk.Label(row, text="Formato de saída:", bg="#333333", fg="white").pack(side="left")
        self.audio_format = tk.StringVar(value="mp3")
        ttk.Combobox(row, textvariable=self.audio_format, values=FORMATS,
                     state="readonly", width=10).pack(side="left", padx=10)
        tk.Label(row, text="Qualidade MP3:", bg="#333333", fg="white").pack(side="left", padx=(15, 0))
        self.mp3_quality = tk.StringVar(value="192")
        ttk.Combobox(row, textvariable=self.mp3_quality, values=MP3_QUALITIES,
                     state="readonly", width=8).pack(side="left", padx=10)
        label("192/256/320 kbps para MP3; outros formatos usam o melhor áudio disponível.")
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
        self.root.after(800, self.poll_clipboard)

    def poll_clipboard(self):
        try:
            copied = self.root.clipboard_get()
            if copied != self.last_clipboard:
                self.last_clipboard = copied
                if self.auto_clipboard.get():
                    existing = [line.strip() for line in self.links.get("1.0", "end").splitlines()]
                    keys = {link_key(url) for url in existing if valid_url(url)}
                    new = []
                    for url in youtube_links(copied):
                        key = link_key(url)
                        if key not in keys:
                            keys.add(key)
                            new.append(url)
                    for url in new[:max(0, MAX_LINKS - len([u for u in existing if u]))]:
                        self.links.insert("end", url + "\n")
                        existing.append(url)
                    if new:
                        self.status.set("Links copiados adicionados à lista. Escolha o formato e clique em Converter.")
        except (tk.TclError, UnicodeError):
            pass
        finally:
            self.root.after(800, self.poll_clipboard)

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
        if not urls:
            messagebox.showwarning("Links", "Informe ao menos um link.")
            return
        bad = [str(i) for i, url in enumerate(urls, 1) if not valid_url(url)]
        if bad:
            messagebox.showwarning("Links", "Link inválido nas linhas: " + ", ".join(bad))
            return
        urls = unique_links(urls)
        if len(urls) > MAX_LINKS:
            messagebox.showwarning("Links", "Informe no máximo 100 vídeos distintos.")
            return
        self.links.delete("1.0", "end")
        self.links.insert("1.0", "\n".join(urls) + "\n")
        if self.audio_format.get() not in FORMATS:
            messagebox.showwarning("Formato", "Selecione um formato de áudio válido.")
            return
        if self.mp3_quality.get() not in MP3_QUALITIES:
            messagebox.showwarning("Qualidade", "Selecione uma qualidade MP3 válida.")
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
        self.table.delete(*self.table.get_children())
        for index, url in enumerate(urls):
            self.table.insert("", "end", iid=str(index), values=(url, "0%", "Aguardando"))
        self.report(f"Iniciando {len(urls)} link(s) em {self.audio_format.get().upper()}.")
        threading.Thread(target=self.worker,
                         args=(urls, folder, self.audio_format.get(), binary,
                               self.mp3_quality.get()), daemon=True).start()

    def worker(self, urls, folder, audio_format, binary, mp3_quality="192"):
        successes = 0
        failures = 0
        for index, url in enumerate(urls, 1):
            self.root.after(0, lambda n=index: (self.progress.configure(value=0),
                           self.table.set(str(n-1), "status", "Baixando"),
                           self.status.set(f"Processando {n}/{len(urls)}: {urls[n-1]}")))

            def hook(data, n=index):
                if data.get("status") == "downloading":
                    total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
                    percent = min(100, 100 * data.get("downloaded_bytes", 0) / total) if total else 0
                    self.root.after(0, lambda p=percent, row=n-1: (
                        self.progress.configure(value=p),
                        self.table.set(str(row), "progress", f"{p:.0f}%")))
                elif data.get("status") == "finished":
                    self.root.after(0, lambda row=n-1: (
                        self.table.set(str(row), "status", "Convertendo"),
                        self.status.set(f"{n}/{len(urls)}: convertendo para {audio_format.upper()}...")))

            try:
                opts = options_for(folder, audio_format, hook, mp3_quality)
                opts["ffmpeg_location"] = binary
                with yt_dlp.YoutubeDL(opts) as downloader:
                    downloader.download([url])
                successes += 1
                self.root.after(0, lambda n=index: (
                    self.table.set(str(n-1), "progress", "100%"),
                    self.table.set(str(n-1), "status", "Pronto"),
                    self.report(f"{n}/{len(urls)}: concluído.")))
            except Exception as exc:
                failures += 1
                error = str(exc)
                self.root.after(0, lambda n=index, e=error: (
                    self.table.set(str(n-1), "status", "Erro"),
                    self.report(f"{n}/{len(urls)}: erro: {e}")))
        self.root.after(0, lambda: self.finish(successes, failures))

    def finish(self, successes, failures):
        self.running = False
        self.start_button.config(state="normal")
        self.status.set(f"Fila concluída: {successes} sucesso(s), {failures} falha(s).")
        messagebox.showinfo("Resultado", self.status.get())


if __name__ == "__main__":
    App(tk.Tk()).root.mainloop()
