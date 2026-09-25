"""Interface para YouTube e TikTok; a extração anterior permanece intacta.

O aplicativo original permanece em main.py, sem modificações.
"""

import json
import html
import os
import re
from pathlib import Path
import shutil
import sys
import threading
import time
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
        ) and (bool(parsed.path.strip("/")) or (parsed.path == "/playlist" and
               bool(parse_qs(parsed.query).get("list"))))
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
    """Encontra links mesmo em texto de compartilhamento, Markdown ou HTML."""
    text = html.unescape(text).replace("\u200b", "").replace("\ufeff", "")
    candidates = re.findall(r"https?://[^\s<>\"']+", text, flags=re.I)
    links = []
    for candidate in candidates:
        url = candidate.rstrip(".,;)]}!?，。")
        if valid_url(url):
            links.append(url)
    return links


def existing_audio(folder, video_id, audio_format):
    """Confere arquivos finalizados pelo ID, sem depender do título mutável."""
    if not video_id or not re.fullmatch(r"[\w-]+", str(video_id)):
        return None
    suffix = f" [{video_id}].{audio_format}".casefold()
    for path in Path(folder).iterdir():
        if path.name.casefold().endswith(suffix) and path.is_file() and path.stat().st_size > 0:
            return path
    return None


def known_video_id(url):
    key = link_key(url)
    if key.startswith(("video:", "tiktok:")):
        return key.split(":", 1)[1]
    return None


def is_playlist_url(url):
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return host.endswith("youtube.com") and bool(parse_qs(parsed.query).get("list"))


def expand_playlist(url):
    """Lista vídeos sem baixar; a fila baixa e converte cada faixa em sequência."""
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "extract_flat": "in_playlist",
                           "skip_download": True, "noplaylist": False,
                           "ignoreerrors": True}) as probe:
        info = probe.extract_info(url, download=False)
    if not info or not info.get("entries"):
        raise RuntimeError("Não foi possível listar os vídeos da playlist.")
    videos = []
    for entry in info["entries"]:
        if not entry:
            continue
        video_id = entry.get("id")
        video_url = entry.get("webpage_url") or entry.get("url") or ""
        if valid_url(video_url) and not is_playlist_url(video_url):
            videos.append(video_url)
        elif video_id and re.fullmatch(r"[\w-]{11}", str(video_id)):
            videos.append("https://www.youtube.com/watch?v=" + str(video_id))
    if not videos:
        raise RuntimeError("A playlist não contém vídeos disponíveis.")
    return videos


def link_key(url):
    """Identifica o mesmo vídeo mesmo com domínio curto ou parâmetros extras."""
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower()
    parts = parsed.path.strip("/").split("/")
    if is_playlist_url(url):
        return "playlist:" + parse_qs(parsed.query)["list"][0]
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

        label("Links de vídeos ou playlists do YouTube e TikTok (até 100 links):")
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
        self.start_button.pack(fill="x", pady=(0, 4))
        tk.Button(frame, text="Minimizar e continuar em segundo plano",
                  command=self.minimize).pack(fill="x", pady=(0, 10))
        self.progress = ttk.Progressbar(frame, maximum=100)
        self.progress.pack(fill="x")
        self.status = tk.StringVar(value="Aguardando...")
        label_status = tk.Label(frame, textvariable=self.status, bg="#333333", fg="white",
                                anchor="w", wraplength=700)
        label_status.pack(fill="x", pady=8)
        self.log = tk.Text(frame, height=6, state="disabled", wrap="word")
        self.log.pack(fill="both")
        self.root.after(800, self.poll_clipboard)

    def minimize(self):
        if self.running:
            self.report("Janela minimizada; a fila continua em segundo plano.")
        self.root.iconify()

    def poll_clipboard(self):
        try:
            try:
                copied = self.root.clipboard_get()
            except tk.TclError:
                copied = self.root.clipboard_get(type="HTML Format")
            if copied != self.last_clipboard:
                self.last_clipboard = copied
                if self.auto_clipboard.get():
                    existing = youtube_links(self.links.get("1.0", "end"))
                    keys = {link_key(url) for url in existing}
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
        raw = self.links.get("1.0", "end")
        urls = unique_links(youtube_links(raw))
        folder = self.folder.get().strip()
        if not urls:
            messagebox.showwarning("Links", "Não encontrei links válidos do YouTube ou TikTok no texto.")
            return
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
        self.report(f"Lendo {len(urls)} link(s) em {self.audio_format.get().upper()}.")
        threading.Thread(target=self.worker,
                         args=(urls, folder, self.audio_format.get(), binary,
                               self.mp3_quality.get()), daemon=True).start()

    def worker(self, urls, folder, audio_format, binary, mp3_quality="192"):
        successes = 0
        failures = 0
        skipped = 0
        expanded = []
        for url in urls:
            if is_playlist_url(url):
                try:
                    entries = expand_playlist(url)
                    expanded.extend(entries)
                    self.root.after(0, lambda count=len(entries): self.report(
                        f"Playlist: {count} vídeo(s) encontrado(s)."))
                except Exception as exc:
                    failures += 1
                    self.root.after(0, lambda error=str(exc): self.report(
                        f"Não foi possível ler playlist: {error}"))
            else:
                expanded.append(url)
        urls = unique_links(expanded)
        self.root.after(0, lambda items=urls: [self.table.insert(
            "", "end", iid=str(i), values=(url, "0%", "Aguardando"))
            for i, url in enumerate(items)])
        self.root.after(0, lambda: self.report(f"Fila preparada: {len(urls)} música(s)."))
        for index, url in enumerate(urls, 1):
            last_update = [0.0, -1]
            self.root.after(0, lambda n=index: (self.progress.configure(value=0),
                           self.table.set(str(n-1), "status", "Baixando"),
                           self.status.set(f"Processando {n}/{len(urls)}: {urls[n-1]}")))

            def hook(data, n=index):
                if data.get("status") == "downloading":
                    total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
                    percent = min(99, 100 * data.get("downloaded_bytes", 0) / total) if total else 0
                    rounded = int(percent)
                    now = time.monotonic()
                    # O extrator envia muitos eventos por segundo; evitar fila de UI atrasada.
                    if rounded == last_update[1] or now - last_update[0] < 0.25:
                        return
                    last_update[:] = [now, rounded]
                    self.root.after(0, lambda p=percent, row=n-1: (
                        self.progress.configure(value=p),
                        self.table.set(str(row), "progress", f"{p:.0f}%")))
                elif data.get("status") == "finished":
                    self.root.after(0, lambda row=n-1: (
                        self.table.set(str(row), "progress", "99%"),
                        self.table.set(str(row), "status", "Convertendo"),
                        self.status.set(f"{n}/{len(urls)}: convertendo para {audio_format.upper()}...")))

            try:
                video_id = known_video_id(url)
                if not video_id:
                    # Links curtos do TikTok precisam ser resolvidos para obter o ID.
                    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True,
                                           "noplaylist": True, "skip_download": True}) as probe:
                        info = probe.extract_info(url, download=False)
                    video_id = info.get("id") if info else None
                found = existing_audio(folder, video_id, audio_format)
                if found:
                    skipped += 1
                    self.root.after(0, lambda n=index, name=found.name: (
                        self.table.set(str(n-1), "progress", "100%"),
                        self.table.set(str(n-1), "status", "Já existe"),
                        self.report(f"{n}/{len(urls)}: {name} já está na pasta; extração ignorada.")))
                    continue
                opts = options_for(folder, audio_format, hook, mp3_quality)
                opts["ffmpeg_location"] = binary
                with yt_dlp.YoutubeDL(opts) as downloader:
                    result = downloader.download([url])
                    if result:
                        raise RuntimeError(f"O extrator retornou código {result}.")
                successes += 1
                self.root.after(0, lambda n=index: (
                    self.table.set(str(n-1), "progress", "100%"),
                    self.table.set(str(n-1), "status", "Pronto"),
                    self.report(f"{n}/{len(urls)}: concluído.")))
            except Exception as exc:
                failures += 1
                error = str(exc)
                self.root.after(0, lambda n=index, e=error: (
                    self.table.set(str(n-1), "progress", "—"),
                    self.table.set(str(n-1), "status", "Erro"),
                    self.report(f"{n}/{len(urls)}: erro: {e}")))
            # O próximo item inicia assim que yt-dlp e a conversão terminam.
        self.root.after(0, lambda: self.finish(successes, failures, skipped))

    def finish(self, successes, failures, skipped=0):
        self.running = False
        self.start_button.config(state="normal")
        self.status.set(f"Fila concluída: {successes} sucesso(s), {skipped} já existente(s), {failures} falha(s).")
        self.report(self.status.get())
        self.root.deiconify()
        self.root.lift()
        self.root.bell()
        messagebox.showinfo("Conversão finalizada", self.status.get(), parent=self.root)


if __name__ == "__main__":
    App(tk.Tk()).root.mainloop()
