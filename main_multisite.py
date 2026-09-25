"""Interface para YouTube, TikTok e Facebook; a extração anterior permanece intacta.

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
import webbrowser
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from urllib.parse import urlparse, parse_qs

import yt_dlp

try:
    from disc_tools import optical_drives, media_files, audio_cd_tracks, convert_file, rip_and_convert
except Exception:
    optical_drives = media_files = audio_cd_tracks = convert_file = rip_and_convert = None


FORMATS = ("mp3", "m4a", "opus", "flac", "wav")
OUTPUT_TYPES = ("Áudio MP3", "Vídeo MP4", "Vídeo AVI", "Vídeo MKV", "Vídeo MOV", "Áudio avançado")
MP3_QUALITIES = ("192", "256", "320")
MAX_LINKS = 1000
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
        facebook = host in (
            "facebook.com", "www.facebook.com", "m.facebook.com", "mbasic.facebook.com",
            "fb.watch", "www.fb.watch"
        ) and bool(parsed.path.strip("/"))
        return parsed.scheme in ("http", "https") and (youtube or tiktok or facebook)
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


def expand_playlist(url, auth=None):
    """Lista vídeos sem baixar; a fila baixa e converte cada faixa em sequência."""
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "extract_flat": "in_playlist",
                           "skip_download": True, "noplaylist": False,
                           "ignoreerrors": True, **(auth or {})}) as probe:
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


def authentication_options(browser, cookie_file):
    """Use only credentials explicitly selected by the user on this computer."""
    if browser == "Sem login":
        return {}
    browser_map = {
        "Chrome": "chrome",
        "Edge": "edge",
        "Firefox": "firefox",
        "Opera": "opera",
        "Brave": "brave",
    }
    if browser in browser_map:
        return {"cookiesfrombrowser": (browser_map[browser],)}
    if browser == "Arquivo cookies.txt":
        path = Path(cookie_file).expanduser()
        if not path.is_file() or path.suffix.lower() != ".txt":
            raise ValueError("Selecione um arquivo cookies.txt válido.")
        return {"cookiefile": str(path)}
    raise ValueError("Selecione uma opção de acesso válida.")


def needs_authentication(error):
    message = str(error).casefold()
    return ("sign in to confirm" in message and "not a bot" in message) or (
        "faça login" in message and "robô" in message)


def cookie_diagnostics(auth):
    """Confirma leitura da sessão sem mostrar nem salvar os valores dos cookies."""
    if not auth:
        return "Sem login selecionado; escolha o navegador em Acesso ao YouTube."
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, **auth}) as probe:
        cookies = list(probe.cookiejar)
    google = [cookie for cookie in cookies if cookie.domain.lstrip(".").endswith(
        ("youtube.com", "google.com"))]
    account = [cookie for cookie in google if cookie.name in (
        "SID", "HSID", "SSID", "APISID", "SAPISID") or cookie.name.startswith(
        "__Secure-1P") or cookie.name.startswith("__Secure-3P")]
    if not account:
        raise RuntimeError(
            "Nenhum cookie de conta do Google/YouTube foi encontrado nessa opção. "
            "Entre no YouTube no navegador escolhido ou selecione um cookies.txt atualizado.")
    return f"Sessão encontrada: {len(account)} cookie(s) de conta; verificando acesso ao vídeo."


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
    if host.endswith("facebook.com") or host in ("fb.watch", "www.fb.watch"):
        return "facebook:" + host + "/" + parsed.path.strip("/") + ("?" + parsed.query if parsed.query else "")
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


def options_for(folder, audio_format, progress_hook, mp3_quality="192", auth=None, output_type="Áudio MP3"):
    options = {
        "noplaylist": True,
        "outtmpl": str(Path(folder) / "%(title).180B [%(id)s].%(ext)s"),
        "ffmpeg_location": ffmpeg_location(),
        "progress_hooks": [progress_hook],
        "quiet": True,
        "no_warnings": True,
        "sleep_interval_requests": 1,
    }
    if output_type.startswith("Vídeo "):
        target = output_type.split()[-1].lower()
        options.update({
            "format": "bestvideo*+bestaudio/best",
            "merge_output_format": "mkv" if target in ("avi", "mov") else target,
        })
        if target in ("avi", "mov"):
            options["postprocessors"] = [{
                "key": "FFmpegVideoConvertor",
                "preferedformat": target,
            }]
    else:
        selected_audio_format = "mp3" if output_type == "Áudio MP3" else audio_format
        options.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": selected_audio_format,
                "preferredquality": mp3_quality if selected_audio_format == "mp3" else "0",
            }],
        })
    options.update(auth or {})
    return options


class App:
    def __init__(self, root):
        self.root = root
        self.running = False
        self.stop_requested = False
        root.title("FluxMídia — Conversor de áudio, vídeo e CD/DVD")
        root.geometry("820x850")
        root.configure(bg="#333333")
        frame = tk.Frame(root, bg="#333333", padx=20, pady=15)
        frame.pack(fill="both", expand=True)

        def label(text):
            tk.Label(frame, text=text, bg="#333333", fg="white", anchor="w").pack(fill="x")

        title = tk.Label(frame, text="FluxMídia", bg="#333333", fg="#45f28b",
                         font=("Segoe UI", 20, "bold"), anchor="w")
        title.pack(fill="x")
        tk.Label(frame, text="Conversor de áudio e vídeo", bg="#333333", fg="white",
                 font=("Segoe UI", 11), anchor="w").pack(fill="x")
        tk.Label(frame, text="Converte CD/DVD", bg="#333333", fg="#9bd8ff",
                 font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x", pady=(0, 8))
        label("Links de vídeos ou playlists do YouTube, TikTok e Facebook (até 1000 links):")
        self.links = tk.Text(frame, height=10, wrap="none")
        self.links.pack(fill="both", expand=True, pady=(5, 12))
        self.auto_clipboard = tk.BooleanVar(value=True)
        tk.Checkbutton(frame, text="Adicionar automaticamente links copiados do YouTube, TikTok ou Facebook",
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
        tk.Label(row, text="Baixar como:", bg="#333333", fg="white").pack(side="left")
        self.output_type = tk.StringVar(value="Áudio MP3")
        ttk.Combobox(row, textvariable=self.output_type, values=OUTPUT_TYPES,
                     state="readonly", width=16).pack(side="left", padx=10)
        self.audio_format = tk.StringVar(value="mp3")
        tk.Label(row, text="Qualidade MP3:", bg="#333333", fg="white").pack(side="left", padx=(15, 0))
        self.mp3_quality = tk.StringVar(value="192")
        ttk.Combobox(row, textvariable=self.mp3_quality, values=MP3_QUALITIES,
                     state="readonly", width=8).pack(side="left", padx=10)
        label("Áudio MP3 usa MP3 automaticamente. Vídeos: MP4, AVI, MKV e MOV.")
        label("Acesso ao YouTube — selecione o navegador em que você fez login:")
        auth_row = tk.Frame(frame, bg="#333333")
        auth_row.pack(fill="x", pady=(4, 8))
        self.browser = tk.StringVar(value="Sem login")
        ttk.Combobox(auth_row, textvariable=self.browser,
                     values=("Sem login", "Chrome", "Edge", "Firefox", "Opera", "Brave", "Arquivo cookies.txt"),
                     state="readonly", width=21).pack(side="left")
        self.cookie_file = tk.StringVar()
        tk.Entry(auth_row, textvariable=self.cookie_file).pack(side="left", fill="x", expand=True, padx=6)
        tk.Button(auth_row, text="Escolher cookies.txt", command=self.select_cookies).pack(side="left")
        tk.Button(frame, text="Testar acesso ao primeiro vídeo", command=self.test_access).pack(
            fill="x", pady=(0, 7))
        login_row = tk.Frame(frame, bg="#333333")
        login_row.pack(fill="x", pady=(0, 7))
        tk.Button(login_row, text="Entrar no YouTube",
                  command=lambda: self.open_login("https://www.youtube.com/")).pack(side="left", expand=True, fill="x", padx=(0, 4))
        tk.Button(login_row, text="Entrar no Facebook",
                  command=lambda: self.open_login("https://www.facebook.com/")).pack(side="left", expand=True, fill="x", padx=4)
        tk.Button(login_row, text="Entrar no TikTok",
                  command=lambda: self.open_login("https://www.tiktok.com/login")).pack(side="left", expand=True, fill="x", padx=(4, 0))
        label("Faça login no navegador escolhido; depois volte ao app. Cookies permanecem no navegador.")
        label("Pasta de destino:")
        folder_row = tk.Frame(frame, bg="#333333")
        folder_row.pack(fill="x", pady=(5, 12))
        self.folder = tk.StringVar(value=self.load_folder())
        tk.Entry(folder_row, textvariable=self.folder).pack(side="left", fill="x", expand=True)
        tk.Button(folder_row, text="Selecionar", command=self.select_folder).pack(side="left", padx=8)
        self.start_button = tk.Button(frame, text="Converter links em sequência", bg="#006600",
                                      fg="white", command=self.start)
        self.start_button.pack(fill="x", pady=(0, 4))
        disc_row = tk.Frame(frame, bg="#333333")
        disc_row.pack(fill="x", pady=(2, 8))
        tk.Button(disc_row, text="💿  Converter CD/DVD", command=self.open_disc_window,
                  bg="#0d5d7a", fg="white", activebackground="#117a9f",
                  activeforeground="white", font=("Segoe UI", 10, "bold"),
                  padx=14, pady=7).pack(fill="x")
        label("Ao minimizar a janela, o aplicativo continua automaticamente em segundo plano.")
        self.progress = ttk.Progressbar(frame, maximum=100)
        self.progress.pack(fill="x")
        self.status = tk.StringVar(value="Aguardando...")
        label_status = tk.Label(frame, textvariable=self.status, bg="#333333", fg="white",
                                anchor="w", wraplength=700)
        label_status.pack(fill="x", pady=8)
        self.log = tk.Text(frame, height=6, state="disabled", wrap="word")
        self.log.pack(fill="both")
        self.root.after(800, self.poll_clipboard)

    def open_disc_window(self):
        if optical_drives is None:
            messagebox.showerror("CD/DVD", "O módulo de CD/DVD não foi carregado.")
            return

        win = tk.Toplevel(self.root)
        win.title("FluxMídia — Converte CD/DVD")
        win.geometry("860x680")
        win.configure(bg="#1f2630")
        win.transient(self.root)

        header = tk.Frame(win, bg="#1f2630", padx=18, pady=14)
        header.pack(fill="x")
        tk.Label(header, text="💿", bg="#1f2630", fg="white",
                 font=("Segoe UI Emoji", 28)).pack(side="left", padx=(0, 10))
        head_text = tk.Frame(header, bg="#1f2630")
        head_text.pack(side="left", fill="x", expand=True)
        tk.Label(head_text, text="Converte CD/DVD", bg="#1f2630", fg="#45f28b",
                 font=("Segoe UI", 18, "bold"), anchor="w").pack(fill="x")
        tk.Label(head_text, text="Ferramentas de disco inspiradas nas funções do K3b, adaptadas para Windows",
                 bg="#1f2630", fg="#c9d6e2", font=("Segoe UI", 10), anchor="w").pack(fill="x")

        body = tk.Frame(win, bg="#1f2630", padx=18, pady=8)
        body.pack(fill="both", expand=True)

        drive_var = tk.StringVar()
        format_var = tk.StringVar(value="mp3")
        status_var = tk.StringVar(value="Insira um CD/DVD e clique em Atualizar unidades.")
        entries = []

        top = tk.LabelFrame(body, text="Unidade óptica", bg="#1f2630", fg="white",
                            padx=10, pady=10)
        top.pack(fill="x", pady=(0, 10))
        tk.Label(top, text="Unidade:", bg="#1f2630", fg="white").pack(side="left")
        drive_box = ttk.Combobox(top, textvariable=drive_var, state="readonly", width=12)
        drive_box.pack(side="left", padx=7)

        def refresh():
            drives = optical_drives()
            drive_box["values"] = drives
            drive_var.set(drives[0] if drives else "")
            status_var.set("Unidades atualizadas." if drives else "Nenhuma unidade de CD/DVD encontrada.")

        tk.Button(top, text="Atualizar unidades", command=refresh).pack(side="left", padx=4)
        tk.Button(top, text="Ejetar", command=lambda: self.eject_drive(drive_var.get(), status_var)).pack(side="left", padx=4)

        actions = tk.LabelFrame(body, text="Operações", bg="#1f2630", fg="white",
                                padx=10, pady=10)
        actions.pack(fill="x", pady=(0, 10))

        tk.Label(actions, text="Formato de saída:", bg="#1f2630", fg="white").grid(row=0, column=0, sticky="w")
        ttk.Combobox(actions, textvariable=format_var,
                     values=("mp3", "wav", "flac", "mp4", "avi"),
                     state="readonly", width=10).grid(row=0, column=1, padx=8, sticky="w")

        list_frame = tk.Frame(body, bg="#1f2630")
        list_frame.pack(fill="both", expand=True, pady=(0, 10))
        items = tk.Listbox(list_frame, selectmode="extended", bg="#10161d", fg="white",
                           selectbackground="#1769ff", height=12)
        items.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(list_frame, command=items.yview)
        sb.pack(side="right", fill="y")
        items.configure(yscrollcommand=sb.set)

        def scan():
            nonlocal entries
            items.delete(0, "end")
            entries = []
            drive = drive_var.get()
            if not drive:
                messagebox.showwarning("CD/DVD", "Selecione uma unidade óptica.", parent=win)
                return
            try:
                files = media_files(drive)
                if files:
                    entries = [("file", p) for p in files[:1000]]
                    for p in files[:1000]:
                        items.insert("end", f"Arquivo: {p.name}")
                    status_var.set(f"{len(entries)} arquivo(s) de mídia encontrado(s).")
                    return
                tracks = audio_cd_tracks(drive)
                entries = [("track", t) for t in tracks]
                for number, start, end in tracks:
                    items.insert("end", f"Faixa de áudio {number:02d} — {(end-start)//75}s")
                status_var.set(f"{len(entries)} faixa(s) de CD de áudio encontrada(s).")
            except Exception as exc:
                messagebox.showerror("CD/DVD", str(exc), parent=win)

        def copy_selected():
            selection = [entries[i] for i in items.curselection()] if entries else []
            if not selection:
                messagebox.showwarning("CD/DVD", "Selecione pelo menos um item.", parent=win)
                return
            folder = self.folder.get().strip()
            if not Path(folder).is_dir():
                messagebox.showwarning("Destino", "Escolha uma pasta de destino válida na tela principal.", parent=win)
                return
            fmt = format_var.get()

            def work():
                ok = 0
                try:
                    ffmpeg = ffmpeg_location()
                    for kind, source in selection:
                        try:
                            if kind == "track":
                                if fmt != "mp3":
                                    raise ValueError("Nesta versão, CD de áudio é extraído em MP3.")
                                result = rip_and_convert(drive_var.get(), [source], folder, ffmpeg,
                                                         lambda number, status: None)
                                if not result or result[0][1] != "concluído":
                                    raise RuntimeError(result[0][1] if result else "Falha ao extrair faixa.")
                            else:
                                dest = Path(folder) / f"Disco {drive_var.get()[0]} - {source.stem}.{fmt}"
                                convert_file(source, dest, fmt, ffmpeg)
                            ok += 1
                        except Exception as exc:
                            self.root.after(0, lambda e=str(exc): self.report("CD/DVD: " + e))
                    self.root.after(0, lambda: status_var.set(f"Concluído: {ok}/{len(selection)} item(ns)."))
                except Exception as exc:
                    self.root.after(0, lambda: status_var.set("Erro: " + str(exc)))

            threading.Thread(target=work, daemon=True).start()

        button_bar = tk.Frame(actions, bg="#1f2630")
        button_bar.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(10, 0))
        tk.Button(button_bar, text="Ler disco", command=scan, bg="#0d5d7a", fg="white",
                  padx=14).pack(side="left", padx=(0, 6))
        tk.Button(button_bar, text="Extrair / converter selecionados", command=copy_selected,
                  bg="#087a37", fg="white", padx=14).pack(side="left", padx=6)
        tk.Button(button_bar, text="Copiar arquivos do disco para pasta",
                  command=lambda: self.copy_disc_files(drive_var.get(), status_var),
                  padx=14).pack(side="left", padx=6)

        advanced = tk.LabelFrame(body, text="Funções do K3b adaptadas", bg="#1f2630", fg="white",
                                 padx=10, pady=10)
        advanced.pack(fill="x")
        tk.Label(advanced,
                 text="Disponível agora: leitura de CD/DVD, extração de CD de áudio, cópia e conversão de mídia.\n"
                      "Gravação de ISO/CD/DVD e apagar mídia RW exigem um motor de gravação nativo do Windows e serão adicionados separadamente.",
                 bg="#1f2630", fg="#c9d6e2", justify="left", anchor="w").pack(fill="x")

        tk.Label(body, textvariable=status_var, bg="#1f2630", fg="#45f28b",
                 anchor="w").pack(fill="x", pady=(10, 0))
        refresh()

    def copy_disc_files(self, drive, status_var):
        if not drive:
            status_var.set("Selecione uma unidade.")
            return
        folder = filedialog.askdirectory(title="Escolha onde copiar os arquivos do CD/DVD")
        if not folder:
            return

        def work():
            try:
                root = Path(drive)
                target = Path(folder) / ("Disco_" + drive[0])
                target.mkdir(parents=True, exist_ok=True)
                count = 0
                for path in root.rglob("*"):
                    if path.is_file():
                        rel = path.relative_to(root)
                        dest = target / rel
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(path, dest)
                        count += 1
                self.root.after(0, lambda: status_var.set(f"{count} arquivo(s) copiado(s) para {target}."))
            except Exception as exc:
                self.root.after(0, lambda: status_var.set("Erro ao copiar disco: " + str(exc)))

        threading.Thread(target=work, daemon=True).start()

    def eject_drive(self, drive, status_var):
        if not drive:
            status_var.set("Selecione uma unidade.")
            return
        try:
            import ctypes
            mci = ctypes.windll.winmm.mciSendStringW
            alias = "fluxmidia_cd"
            mci(f'open {drive[0]}: type cdaudio alias {alias}', None, 0, None)
            mci(f'set {alias} door open', None, 0, None)
            mci(f'close {alias}', None, 0, None)
            status_var.set("Bandeja ejetada.")
        except Exception as exc:
            status_var.set("Não foi possível ejetar: " + str(exc))

    def minimize(self):
        if self.running:
            self.report("Janela minimizada; a fila continua em segundo plano.")
        self.root.iconify()

    def open_login(self, url):
        try:
            webbrowser.open_new_tab(url)
            self.status.set("Navegador aberto para login. Depois de entrar, volte ao aplicativo.")
        except Exception as exc:
            messagebox.showerror("Login", f"Não foi possível abrir o navegador: {exc}")

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

    def select_cookies(self):
        file = filedialog.askopenfilename(filetypes=[("Cookies do navegador", "*.txt")])
        if file:
            self.cookie_file.set(file)
            self.browser.set("Arquivo cookies.txt")

    def test_access(self):
        if self.running:
            return
        urls = youtube_links(self.links.get("1.0", "end"))
        if not urls:
            messagebox.showwarning("Teste", "Cole um link de vídeo ou playlist antes do teste.")
            return
        try:
            auth = authentication_options(self.browser.get(), self.cookie_file.get())
        except ValueError as exc:
            messagebox.showerror("Acesso", str(exc))
            return
        self.running = True
        self.start_button.config(state="disabled")
        self.status.set("Testando acesso, sem baixar músicas...")
        threading.Thread(target=self.access_worker, args=(urls[0], auth), daemon=True).start()

    def access_worker(self, url, auth):
        try:
            detail = cookie_diagnostics(auth)
            self.root.after(0, lambda: self.report(detail))
            if not auth:
                raise RuntimeError(detail)
            if is_playlist_url(url):
                url = expand_playlist(url, auth)[0]
            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True,
                                   "noplaylist": True, **auth}) as probe:
                info = probe.extract_info(url, download=False)
            if not info or not info.get("formats"):
                raise RuntimeError("Acesso confirmado parcialmente, mas nenhum áudio foi oferecido.")
            result = "Teste OK: sessão lida e formatos disponíveis para o primeiro vídeo."
        except Exception as exc:
            result = "Teste falhou: " + str(exc)
        self.root.after(0, lambda: self.finish_access_test(result))

    def finish_access_test(self, result):
        self.running = False
        self.start_button.config(state="normal")
        self.status.set(result)
        self.report(result)

    def report(self, line):
        self.log.config(state="normal")
        self.log.insert("end", line + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def stop_conversion(self):
        if not self.running:
            self.status.set("Nenhuma conversão em andamento.")
            return
        self.stop_requested = True
        self.status.set("Parando a conversão com segurança...")
        self.report("Parada solicitada pelo usuário. Finalizando a operação atual.")

    def shutdown_app(self):
        if self.running:
            if not messagebox.askyesno(
                "Desligar FluxMídia",
                "Há uma conversão em andamento. Deseja parar a conversão e desligar o FluxMídia?",
                parent=self.root,
            ):
                return
            self.stop_requested = True
        self.root.destroy()

    def start(self):
        if self.running:
            return
        self.stop_requested = False
        raw = self.links.get("1.0", "end")
        urls = unique_links(youtube_links(raw))
        folder = self.folder.get().strip()
        if not urls:
            messagebox.showwarning("Links", "Não encontrei links válidos do YouTube, TikTok ou Facebook no texto.")
            return
        if len(urls) > MAX_LINKS:
            messagebox.showwarning("Links", "Informe no máximo 1000 vídeos distintos.")
            return
        self.links.delete("1.0", "end")
        self.links.insert("1.0", "\n".join(urls) + "\n")
        if self.output_type.get() not in OUTPUT_TYPES:
            messagebox.showwarning("Formato", "Selecione um formato de saída válido.")
            return
        if self.output_type.get() == "Áudio avançado" and self.audio_format.get() not in FORMATS:
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
            auth = authentication_options(self.browser.get(), self.cookie_file.get())
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            CONFIG.write_text(json.dumps({"destination_folder": folder}), encoding="utf-8")
        except (OSError, ValueError) as exc:
            messagebox.showerror("Preparação", str(exc))
            return
        self.running = True
        self.start_button.config(state="disabled")
        self.progress.configure(value=0)
        self.table.delete(*self.table.get_children())
        selected_label = self.output_type.get()
        if selected_label == "Áudio avançado":
            selected_label = self.audio_format.get().upper()
        self.report(f"Lendo {len(urls)} link(s) em {selected_label}.")
        self.report("Acesso selecionado: " + self.browser.get())
        threading.Thread(target=self.worker,
                         args=(urls, folder, self.audio_format.get(), binary,
                               self.mp3_quality.get(), auth, self.output_type.get()), daemon=True).start()

    def worker(self, urls, folder, audio_format, binary, mp3_quality="192", auth=None, output_type="Áudio MP3"):
        successes = 0
        failures = 0
        skipped = 0
        paused = False
        stopped = False
        try:
            detail = cookie_diagnostics(auth)
            self.root.after(0, lambda message=detail: self.report(message))
        except Exception as exc:
            self.root.after(0, lambda message=str(exc): self.report("Falha na sessão: " + message))
            self.root.after(0, lambda: self.finish(0, 1, 0, True))
            return
        expanded = []
        for url in urls:
            if is_playlist_url(url):
                try:
                    entries = expand_playlist(url, auth)
                    expanded.extend(entries)
                    self.root.after(0, lambda count=len(entries): self.report(
                        f"Playlist: {count} vídeo(s) encontrado(s)."))
                except Exception as exc:
                    failures += 1
                    self.root.after(0, lambda error=str(exc): self.report(
                        f"Não foi possível ler playlist: {error}"))
                    if needs_authentication(exc):
                        paused = True
                        break
            else:
                expanded.append(url)
        urls = unique_links(expanded)
        if paused:
            urls = []
            self.root.after(0, lambda: self.report(
                "Playlist exige confirmação do YouTube. Escolha um navegador com sessão ativa ou cookies.txt e tente novamente."))
        self.root.after(0, lambda items=urls: [self.table.insert(
            "", "end", iid=str(i), values=(url, "0%", "Aguardando"))
            for i, url in enumerate(items)])
        self.root.after(0, lambda: self.report(f"Fila preparada: {len(urls)} música(s)."))
        for index, url in enumerate(urls, 1):
            if self.stop_requested:
                stopped = True
                self.root.after(0, lambda: self.report("Conversão interrompida pelo usuário."))
                break
            last_update = [0.0, -1]
            self.root.after(0, lambda n=index: (self.progress.configure(value=0),
                           self.table.set(str(n-1), "status", "Baixando"),
                           self.status.set(f"Processando {n}/{len(urls)}: {urls[n-1]}")))

            def hook(data, n=index):
                if self.stop_requested:
                    raise RuntimeError("Conversão interrompida pelo usuário.")
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
                        self.status.set(f"{n}/{len(urls)}: finalizando {output_type if output_type != 'Áudio avançado' else audio_format.upper()}...")))

            try:
                video_id = known_video_id(url)
                if not video_id:
                    # Links curtos do TikTok precisam ser resolvidos para obter o ID.
                    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True,
                                           "noplaylist": True, "skip_download": True,
                                           **(auth or {})}) as probe:
                        info = probe.extract_info(url, download=False)
                    video_id = info.get("id") if info else None
                effective_audio_format = "mp3" if output_type == "Áudio MP3" else audio_format
                found = None if output_type.startswith("Vídeo ") else existing_audio(folder, video_id, effective_audio_format)
                if found:
                    skipped += 1
                    self.root.after(0, lambda n=index, name=found.name: (
                        self.table.set(str(n-1), "progress", "100%"),
                        self.table.set(str(n-1), "status", "Já existe"),
                        self.report(f"{n}/{len(urls)}: {name} já está na pasta; extração ignorada.")))
                    continue
                opts = options_for(folder, audio_format, hook, mp3_quality, auth, output_type)
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
                if self.stop_requested:
                    stopped = True
                    self.root.after(0, lambda: self.report("Conversão interrompida pelo usuário."))
                    break
                failures += 1
                error = str(exc)
                blocked = needs_authentication(error)
                self.root.after(0, lambda n=index, e=error, b=blocked: (
                    self.table.set(str(n-1), "progress", "—"),
                    self.table.set(str(n-1), "status", "Acesso" if b else "Erro"),
                    self.report(f"{n}/{len(urls)}: erro: {e}")))
                if blocked:
                    paused = True
                    advice = ("A opção 'Sem login' está ativa. Escolha o navegador em que você entrou no YouTube "
                              "e use 'Testar acesso ao primeiro vídeo'." if not auth else
                              "A sessão foi lida, mas o YouTube recusou o vídeo. Abra esse vídeo no navegador "
                              "e conclua a verificação solicitada. Se persistir, tente um cookies.txt recente "
                              "e use 'Testar acesso ao primeiro vídeo'.")
                    self.root.after(0, lambda message=advice: self.report(message))
                    break
            # O próximo item inicia assim que yt-dlp e a conversão terminam.
        self.root.after(0, lambda: self.finish(successes, failures, skipped, paused, stopped))

    def finish(self, successes, failures, skipped=0, paused=False, stopped=False):
        self.running = False
        self.stop_requested = False
        self.start_button.config(state="normal")
        state = ("Conversão interrompida pelo usuário" if stopped else
                 "Fila interrompida por confirmação do YouTube" if paused else "Fila concluída")
        self.status.set(f"{state}: {successes} sucesso(s), {skipped} já existente(s), {failures} falha(s).")
        self.report(self.status.get())
        self.root.deiconify()
        self.root.lift()
        self.root.bell()
        messagebox.showinfo("Conversão finalizada", self.status.get(), parent=self.root)


if __name__ == "__main__":
    App(tk.Tk()).root.mainloop()
