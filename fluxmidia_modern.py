"""FluxMídia - interface moderna para Windows.

Esta camada apenas substitui a interface visual. O motor de download/conversão
permanece em main_multisite.py e o módulo de CD/DVD permanece em disc_tools.py.
"""

import os
from pathlib import Path
import shutil
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from urllib.parse import urlparse

from main_multisite import (
    App,
    MAX_LINKS,
    MP3_QUALITIES,
    VIDEO_QUALITIES,
    optical_drives,
    media_files,
    audio_cd_tracks,
    convert_file,
    rip_and_convert,
    ffmpeg_location,
)

BG = "#061421"
PANEL = "#0a1b2a"
PANEL2 = "#0d2235"
BORDER = "#1f4c68"
TEXT = "#f4f7fb"
MUTED = "#a8bac8"
CYAN = "#19c6ff"
GREEN = "#00e676"
GREEN2 = "#00b95c"
BLUE = "#1769ff"
RED = "#ff2d3a"
PURPLE = "#7b2cbf"
ENTRY = "#07111c"


class ModernApp(App):
    def __init__(self, root):
        self.root = root
        self.running = False
        self.stop_requested = False
        self.last_clipboard = None
        self.platform_mode = "YouTube"

        root.title("FluxMídia — Conversor de áudio, vídeo e CD/DVD")
        root.geometry("1120x850")
        root.minsize(980, 720)
        root.configure(bg=BG)

        self._style()

        outer = tk.Frame(root, bg=BG, padx=12, pady=10)
        outer.pack(fill="both", expand=True)

        self._header(outer)
        self._links_panel(outer)
        self._table_panel(outer)
        self._options_panel(outer)
        self._destination_panel(outer)
        self._footer(outer)

        self.root.after(800, self.poll_clipboard)

    def select_platform(self, platform):
        self.platform_mode = platform
        labels = {
            "YouTube": "▶  YouTube — cole links de vídeos ou playlists",
            "TikTok": "♪  TikTok — cole um ou mais links públicos para baixar",
            "Facebook": "f  Facebook — cole um ou mais links públicos para baixar",
        }
        if hasattr(self, "platform_label"):
            self.platform_label.config(text=f"{labels.get(platform, platform)} (até {MAX_LINKS} links)")
        if hasattr(self, "status"):
            backend = "motor atual do YouTube" if platform == "YouTube" else "motor Social-Media-Downloader integrado"
            self.status.set(f"{platform} selecionado — {backend}.")
        if hasattr(self, "links"):
            self.links.focus_set()

    def _platform_from_url(self, url):
        try:
            host = (urlparse(url).hostname or "").lower()
        except ValueError:
            return None
        if "tiktok.com" in host:
            return "TikTok"
        if "facebook.com" in host or host.endswith("fb.watch"):
            return "Facebook"
        if "youtube.com" in host or "youtu.be" in host:
            return "YouTube"
        return None

    def poll_clipboard(self):
        try:
            try:
                copied = self.root.clipboard_get()
            except tk.TclError:
                copied = self.root.clipboard_get(type="HTML Format")
            if copied != self.last_clipboard:
                self.last_clipboard = copied
                if self.auto_clipboard.get():
                    from main_multisite import youtube_links, link_key
                    existing = youtube_links(self.links.get("1.0", "end"))
                    keys = {link_key(url) for url in existing}
                    new = []
                    for url in youtube_links(copied):
                        key = link_key(url)
                        if key not in keys:
                            keys.add(key)
                            new.append(url)
                    for url in new[:max(0, MAX_LINKS - len(existing))]:
                        self.links.insert("end", url + "\n")
                        existing.append(url)
                    if new:
                        platform = self._platform_from_url(new[0])
                        if platform:
                            self.select_platform(platform)
                        self.status.set(
                            f"{platform or 'Link'} detectado da área de transferência e enviado para a tela de baixar."
                        )
        except (tk.TclError, UnicodeError):
            pass
        finally:
            self.root.after(800, self.poll_clipboard)

    def _style(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            "Flux.Treeview",
            background=ENTRY,
            fieldbackground=ENTRY,
            foreground=TEXT,
            rowheight=31,
            borderwidth=0,
            font=("Segoe UI", 10),
        )
        style.map("Flux.Treeview", background=[("selected", "#113b5a")])
        style.configure(
            "Flux.Treeview.Heading",
            background="#10283c",
            foreground=TEXT,
            relief="flat",
            font=("Segoe UI", 10, "bold"),
            padding=(8, 7),
        )
        style.map("Flux.Treeview.Heading", background=[("active", "#143651")])
        style.configure(
            "Flux.TCombobox",
            fieldbackground="#10283c",
            background="#10283c",
            foreground=TEXT,
            arrowcolor=TEXT,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            padding=7,
        )
        style.map(
            "Flux.TCombobox",
            fieldbackground=[("readonly", "#10283c")],
            foreground=[("readonly", TEXT)],
            selectbackground=[("readonly", "#10283c")],
            selectforeground=[("readonly", TEXT)],
        )
        style.configure(
            "Flux.Horizontal.TProgressbar",
            troughcolor="#183149",
            background=GREEN,
            bordercolor="#183149",
            lightcolor=GREEN,
            darkcolor=GREEN,
            thickness=12,
        )

    def _card(self, parent, padx=12, pady=10):
        return tk.Frame(
            parent,
            bg=PANEL,
            highlightthickness=1,
            highlightbackground=BORDER,
            padx=padx,
            pady=pady,
        )

    def _button(self, parent, text, command, bg=PANEL2, fg=TEXT, width=None):
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=("#124f35" if bg == GREEN2 else "#15344c"),
            activeforeground="white",
            relief="flat",
            bd=0,
            cursor="hand2",
            font=("Segoe UI", 10, "bold"),
            padx=14,
            pady=9,
            width=width,
        )

    def _header(self, parent):
        head = tk.Frame(parent, bg=BG)
        head.pack(fill="x", pady=(0, 10))

        brand = tk.Frame(head, bg=BG)
        brand.pack(side="left")
        tk.Label(
            brand,
            text="▶♫↓",
            bg="#09233a",
            fg=GREEN,
            font=("Segoe UI Symbol", 25, "bold"),
            padx=10,
            pady=5,
        ).pack(side="left", padx=(0, 10))
        titles = tk.Frame(brand, bg=BG)
        titles.pack(side="left")
        tk.Label(
            titles,
            text="FluxMídia",
            bg=BG,
            fg=TEXT,
            font=("Segoe UI", 27, "bold"),
            anchor="w",
        ).pack(anchor="w")
        tk.Label(
            titles,
            text="Conversor de áudio e vídeo   •   Converte CD/DVD",
            bg=BG,
            fg=CYAN,
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w")

        nav = tk.Frame(head, bg=BG)
        nav.pack(side="right")
        self._button(nav, "▶  YouTube", lambda: self.select_platform("YouTube"), bg="#182638").pack(side="left", padx=3)
        self._button(nav, "♪  TikTok", lambda: self.select_platform("TikTok"), bg="#182638").pack(side="left", padx=3)
        self._button(nav, "f  Facebook", lambda: self.select_platform("Facebook"), bg="#182638").pack(side="left", padx=3)
        self._button(nav, "💿  Converte\nCD/DVD", self.open_disc_window, bg="#103e32").pack(side="left", padx=3)

    def _links_panel(self, parent):
        card = self._card(parent)
        card.pack(fill="x", pady=(0, 8))

        self.platform_label = tk.Label(
            card,
            text=f"▶  YouTube — cole links de vídeos ou playlists (até {MAX_LINKS} links)",
            bg=PANEL,
            fg=CYAN,
            font=("Segoe UI", 11, "bold"),
            anchor="w",
        )
        self.platform_label.pack(fill="x")
        tk.Label(
            card,
            text="TikTok e Facebook usam o motor Social-Media-Downloader integrado; YouTube mantém o motor atual.",
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI", 8),
            anchor="w",
        ).pack(fill="x", pady=(2, 0))

        self.links = tk.Text(
            card,
            height=4,
            wrap="none",
            bg=ENTRY,
            fg=TEXT,
            insertbackground=TEXT,
            selectbackground=BLUE,
            relief="flat",
            bd=0,
            font=("Consolas", 10),
            padx=10,
            pady=8,
        )
        self.links.pack(fill="x", pady=(7, 7))

        self.auto_clipboard = tk.BooleanVar(value=True)
        tk.Checkbutton(
            card,
            text="Adicionar automaticamente links copiados do YouTube, TikTok ou Facebook",
            variable=self.auto_clipboard,
            bg=PANEL,
            fg=TEXT,
            selectcolor=GREEN2,
            activebackground=PANEL,
            activeforeground=TEXT,
            font=("Segoe UI", 9),
        ).pack(anchor="w")

    def _table_panel(self, parent):
        card = self._card(parent)
        card.pack(fill="both", expand=True, pady=(0, 8))

        tk.Label(
            card,
            text="🔗  Progresso por link:",
            bg=PANEL,
            fg=TEXT,
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 5))

        table_frame = tk.Frame(card, bg=PANEL)
        table_frame.pack(fill="both", expand=True)

        self.table = ttk.Treeview(
            table_frame,
            columns=("link", "progress", "status"),
            show="headings",
            style="Flux.Treeview",
            height=7,
        )
        self.table.heading("link", text="Link")
        self.table.heading("progress", text="Progresso")
        self.table.heading("status", text="Resultado")
        self.table.column("link", width=650, stretch=True)
        self.table.column("progress", width=130, stretch=False, anchor="center")
        self.table.column("status", width=125, stretch=False, anchor="center")
        self.table.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(table_frame, command=self.table.yview)
        sb.pack(side="right", fill="y")
        self.table.configure(yscrollcommand=sb.set)

    def _options_panel(self, parent):
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", pady=(0, 8))
        row.grid_columnconfigure(0, weight=1)
        row.grid_columnconfigure(1, weight=1)

        left = self._card(row)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        right = self._card(row)
        right.grid(row=0, column=1, sticky="nsew", padx=(4, 0))

        tk.Label(left, text="♫  Opções de download:", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 10, "bold")).grid(row=0, column=0, columnspan=4, sticky="w")

        tk.Label(left, text="Baixar como:", bg=PANEL, fg=TEXT).grid(row=1, column=0, sticky="w", pady=(10, 0))
        self.output_type = tk.StringVar(value="Áudio MP3")
        self.output_box = ttk.Combobox(
            left,
            textvariable=self.output_type,
            values=("Áudio MP3", "Vídeo MP4", "Vídeo AVI", "Vídeo MKV", "Vídeo MOV"),
            state="readonly",
            width=16,
            style="Flux.TCombobox",
        )
        self.output_box.grid(row=1, column=1, sticky="w", padx=7, pady=(10, 0))

        self.audio_format = tk.StringVar(value="mp3")
        self.quality_label = tk.Label(left, text="Qualidade MP3:", bg=PANEL, fg=TEXT)
        self.quality_label.grid(row=1, column=2, sticky="w", padx=(15, 0), pady=(10, 0))
        self.mp3_quality = tk.StringVar(value="320")
        self.video_quality = tk.StringVar(value="1080p")
        self.quality_box = ttk.Combobox(
            left,
            textvariable=self.mp3_quality,
            values=MP3_QUALITIES,
            state="readonly",
            width=10,
            style="Flux.TCombobox",
        )
        self.quality_box.grid(row=1, column=3, sticky="w", padx=7, pady=(10, 0))
        self.output_box.bind("<<ComboboxSelected>>", self._on_output_type_changed)

        self.download_hint = tk.Label(
            left,
            text="ⓘ  Áudio MP3 usa MP3 automaticamente. Vídeos permitem escolher a resolução.",
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI", 8),
        )
        self.download_hint.grid(row=2, column=0, columnspan=4, sticky="w", pady=(10, 0))

        tk.Label(right, text="🔒  Acesso e login das plataformas:", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")

        browser_row = tk.Frame(right, bg=PANEL)
        browser_row.pack(fill="x", pady=(10, 6))
        tk.Label(browser_row, text="Navegador para login:", bg=PANEL, fg=TEXT).pack(side="left")
        self.browser = tk.StringVar(value="Sem login")
        ttk.Combobox(
            browser_row,
            textvariable=self.browser,
            values=("Sem login", "Chrome", "Edge", "Firefox", "Opera", "Brave", "Arquivo cookies.txt"),
            state="readonly",
            width=22,
            style="Flux.TCombobox",
        ).pack(side="left", padx=8)

        self.cookie_file = tk.StringVar()
        self._button(browser_row, "cookies.txt", self.select_cookies, bg="#173047").pack(side="right")

        login_row = tk.Frame(right, bg=PANEL)
        login_row.pack(fill="x")
        self._button(login_row, "▶ YouTube", lambda: self.open_login("https://www.youtube.com/"), bg="#8f1d28").pack(side="left", expand=True, fill="x", padx=(0, 3))
        self._button(login_row, "f Facebook", lambda: self.open_login("https://www.facebook.com/"), bg="#174ea6").pack(side="left", expand=True, fill="x", padx=3)
        self._button(login_row, "♪ TikTok", lambda: self.open_login("https://www.tiktok.com/login"), bg="#202a34").pack(side="left", expand=True, fill="x", padx=(3, 0))

        self._button(right, "Testar acesso ao primeiro vídeo", self.test_access, bg="#173047").pack(fill="x", pady=(7, 0))

    def _on_output_type_changed(self, event=None):
        if self.output_type.get().startswith("Vídeo "):
            self.quality_label.config(text="Qualidade do vídeo:")
            self.quality_box.config(textvariable=self.video_quality, values=VIDEO_QUALITIES)
            if self.video_quality.get() not in VIDEO_QUALITIES:
                self.video_quality.set("1080p")
            self.download_hint.config(
                text="ⓘ  Vídeo: escolha a resolução. No YouTube, playlists ficam desativadas neste modo."
            )
        else:
            self.quality_label.config(text="Qualidade MP3:")
            self.quality_box.config(textvariable=self.mp3_quality, values=MP3_QUALITIES)
            if self.mp3_quality.get() not in MP3_QUALITIES:
                self.mp3_quality.set("320")
            self.download_hint.config(
                text="ⓘ  Áudio MP3 usa MP3 automaticamente. Playlists do YouTube continuam disponíveis."
            )

    def _destination_panel(self, parent):
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", pady=(0, 8))
        row.grid_columnconfigure(0, weight=3)
        row.grid_columnconfigure(1, weight=1)

        dest = self._card(row)
        dest.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        extras = self._card(row)
        extras.grid(row=0, column=1, sticky="nsew", padx=(4, 0))

        tk.Label(dest, text="📁  Pasta de destino:", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")

        destrow = tk.Frame(dest, bg=PANEL)
        destrow.pack(fill="x", pady=(8, 8))
        self.folder = tk.StringVar(value=self.load_folder())
        tk.Entry(
            destrow,
            textvariable=self.folder,
            bg=ENTRY,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            bd=0,
            font=("Segoe UI", 10),
        ).pack(side="left", fill="x", expand=True, ipady=7)
        self._button(destrow, "📁 Selecionar", self.select_folder, bg="#173047").pack(side="left", padx=(8, 0))

        actionrow = tk.Frame(dest, bg=PANEL)
        actionrow.pack(fill="x")
        self.start_button = self._button(actionrow, "▶  Converter links em sequência", self.start, bg=GREEN2)
        self.start_button.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.stop_button = self._button(actionrow, "■  Parar conversão", self.stop_conversion, bg="#a1262f")
        self.stop_button.pack(side="left", padx=4)
        self.shutdown_button = self._button(actionrow, "⏻  Desligar", self.shutdown_app, bg="#5f1d7a")
        self.shutdown_button.pack(side="left", padx=(4, 0))

        tk.Label(extras, text="⚙  Opções adicionais:", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        for txt in (
            "✓ Minimizar e continuar em segundo plano",
            "✓ Manter nomes originais",
            "✓ Processar fila em sequência",
        ):
            tk.Label(extras, text=txt, bg=PANEL, fg=TEXT, anchor="w",
                     font=("Segoe UI", 9)).pack(fill="x", pady=3)

    def _footer(self, parent):
        self.progress = ttk.Progressbar(parent, maximum=100, style="Flux.Horizontal.TProgressbar")
        self.progress.pack(fill="x", pady=(0, 5))

        statusrow = tk.Frame(parent, bg=BG)
        statusrow.pack(fill="x")
        self.status = tk.StringVar(value="Aguardando...")
        tk.Label(statusrow, textvariable=self.status, bg=BG, fg=MUTED,
                 font=("Segoe UI", 9), anchor="w").pack(side="left", fill="x", expand=True)

        self.log = tk.Text(
            parent,
            height=4,
            state="disabled",
            wrap="word",
            bg=ENTRY,
            fg=MUTED,
            insertbackground=TEXT,
            relief="flat",
            bd=0,
            font=("Consolas", 9),
            padx=8,
            pady=6,
        )
        self.log.pack(fill="x", pady=(5, 0))

    def open_disc_window(self):
        if optical_drives is None:
            messagebox.showerror("CD/DVD", "O módulo de CD/DVD não foi carregado.")
            return

        win = tk.Toplevel(self.root)
        win.title("FluxMídia — Converte CD/DVD")
        win.geometry("900x760")
        win.minsize(780, 640)
        win.configure(bg=BG)

        outer = tk.Frame(win, bg=BG, padx=12, pady=10)
        outer.pack(fill="both", expand=True)

        header = tk.Frame(outer, bg=BG)
        header.pack(fill="x", pady=(0, 8))
        tk.Label(header, text="💿", bg=BG, fg=TEXT, font=("Segoe UI Emoji", 28)).pack(side="left")
        htxt = tk.Frame(header, bg=BG)
        htxt.pack(side="left", padx=10)
        tk.Label(htxt, text="FluxMídia — Converte CD/DVD", bg=BG, fg=TEXT,
                 font=("Segoe UI", 19, "bold")).pack(anchor="w")
        tk.Label(htxt, text="Leitura, extração, cópia e ferramentas de gravação do Windows",
                 bg=BG, fg=CYAN, font=("Segoe UI", 9)).pack(anchor="w")

        drive_var = tk.StringVar()
        format_var = tk.StringVar(value="mp3")
        quality_var = tk.StringVar(value="320")
        status_var = tk.StringVar(value="Insira um CD/DVD e clique em Ler faixas do CD.")
        entries = []

        toolbar = self._card(outer, padx=7, pady=7)
        toolbar.pack(fill="x", pady=(0, 8))

        def tool(text, cmd, active=False):
            b = self._button(toolbar, text, cmd, bg=(BLUE if active else "#132b40"))
            b.pack(side="left", padx=3, fill="x", expand=True)
            return b

        # Body must exist before toolbar callbacks are used.
        body = self._card(outer)
        body.pack(fill="both", expand=True)

        settings = tk.Frame(body, bg=PANEL)
        settings.pack(fill="x")

        left = tk.Frame(settings, bg=PANEL)
        left.pack(side="left", fill="both", expand=True)
        right = tk.Frame(settings, bg=PANEL)
        right.pack(side="right", fill="y", padx=(14, 0))

        tk.Label(left, text="Extrair Áudio do CD", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 16, "bold")).pack(anchor="w")
        tk.Label(left, text="Converta faixas de CD de áudio para MP3. Arquivos de discos de dados também podem ser convertidos.",
                 bg=PANEL, fg=MUTED, wraplength=500, justify="left").pack(anchor="w", pady=(2, 10))

        form = tk.Frame(left, bg=PANEL)
        form.pack(fill="x")
        tk.Label(form, text="Unidade de CD/DVD:", bg=PANEL, fg=TEXT).grid(row=0, column=0, sticky="w", pady=4)
        drive_box = ttk.Combobox(form, textvariable=drive_var, state="readonly", width=32, style="Flux.TCombobox")
        drive_box.grid(row=0, column=1, sticky="ew", padx=8, pady=4)

        tk.Label(form, text="Formato de saída:", bg=PANEL, fg=TEXT).grid(row=1, column=0, sticky="w", pady=4)
        ttk.Combobox(form, textvariable=format_var, values=("mp3", "wav", "flac", "mp4", "avi"),
                     state="readonly", width=18, style="Flux.TCombobox").grid(row=1, column=1, sticky="w", padx=8, pady=4)

        tk.Label(form, text="Qualidade:", bg=PANEL, fg=TEXT).grid(row=2, column=0, sticky="w", pady=4)
        ttk.Combobox(form, textvariable=quality_var, values=("192", "256", "320"),
                     state="readonly", width=18, style="Flux.TCombobox").grid(row=2, column=1, sticky="w", padx=8, pady=4)
        form.grid_columnconfigure(1, weight=1)

        tk.Label(right, text="💿", bg=PANEL, fg=CYAN, font=("Segoe UI Emoji", 72)).pack(padx=20, pady=10)

        list_frame = tk.Frame(body, bg=PANEL)
        list_frame.pack(fill="both", expand=True, pady=(12, 8))
        items = tk.Listbox(
            list_frame,
            selectmode="extended",
            bg=ENTRY,
            fg=TEXT,
            selectbackground=BLUE,
            relief="flat",
            bd=0,
            font=("Segoe UI", 10),
        )
        items.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(list_frame, command=items.yview)
        sb.pack(side="right", fill="y")
        items.configure(yscrollcommand=sb.set)

        def refresh():
            drives = optical_drives()
            drive_box["values"] = drives
            drive_var.set(drives[0] if drives else "")
            status_var.set("Unidade detectada." if drives else "Nenhuma unidade de CD/DVD encontrada.")

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
                        items.insert("end", f"  Arquivo   {p.name}")
                    status_var.set(f"{len(entries)} arquivo(s) de mídia encontrado(s).")
                    return
                tracks = audio_cd_tracks(drive)
                entries = [("track", t) for t in tracks]
                for number, start, end in tracks:
                    duration = max(0, (end - start) // 75)
                    items.insert("end", f"  ✓  Faixa {number:02d}     {duration//60:02d}:{duration%60:02d}")
                status_var.set(f"{len(entries)} faixa(s) de áudio encontrada(s).")
            except Exception as exc:
                messagebox.showerror("CD/DVD", str(exc), parent=win)

        def copy_selected():
            selection = [entries[i] for i in items.curselection()] if entries else []
            if not selection:
                messagebox.showwarning("CD/DVD", "Selecione pelo menos um item.", parent=win)
                return
            folder = self.folder.get().strip()
            if not Path(folder).is_dir():
                folder = filedialog.askdirectory(parent=win, title="Pasta de destino")
                if not folder:
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
                                    raise ValueError("Faixas de CD de áudio são extraídas em MP3 nesta versão.")
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

        def burn_iso():
            iso = filedialog.askopenfilename(parent=win, title="Selecione a imagem ISO",
                                             filetypes=[("Imagem ISO", "*.iso")])
            if not iso:
                return
            burner = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "isoburn.exe"
            if not burner.exists():
                messagebox.showerror("Gravar ISO", "O gravador de imagem do Windows não foi encontrado.", parent=win)
                return
            subprocess.Popen([str(burner), iso])
            status_var.set("Gravador de ISO do Windows aberto.")

        def burn_data():
            selected = filedialog.askopenfilenames(parent=win, title="Selecione arquivos para gravar")
            if not selected:
                return
            burn_dir = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Microsoft" / "Windows" / "Burn" / "Burn"
            burn_dir.mkdir(parents=True, exist_ok=True)
            copied = 0
            for src in selected:
                try:
                    shutil.copy2(src, burn_dir / Path(src).name)
                    copied += 1
                except OSError:
                    pass
            subprocess.Popen(["explorer.exe", "shell:CD Burning"])
            status_var.set(f"{copied} arquivo(s) preparados. Use a janela do Windows para concluir a gravação.")

        def burn_audio():
            wm = shutil.which("wmplayer.exe")
            if wm:
                subprocess.Popen([wm, "/Task", "Burn"])
                status_var.set("Ferramenta de gravação de áudio do Windows aberta.")
            else:
                burn_data()
                status_var.set("Media Player clássico não encontrado; arquivos foram enviados ao assistente de gravação do Windows.")

        def more_tools():
            menu = tk.Toplevel(win)
            menu.title("FluxMídia — Mais ferramentas")
            menu.geometry("430x300")
            menu.configure(bg=BG)
            p = self._card(menu)
            p.pack(fill="both", expand=True, padx=12, pady=12)
            tk.Label(p, text="Mais ferramentas de CD/DVD", bg=PANEL, fg=TEXT,
                     font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 10))
            self._button(p, "⏏  Ejetar bandeja", lambda: self.eject_drive(drive_var.get(), status_var), bg="#173047").pack(fill="x", pady=4)
            self._button(p, "📁  Abrir pasta de gravação do Windows", lambda: subprocess.Popen(["explorer.exe", "shell:CD Burning"]), bg="#173047").pack(fill="x", pady=4)
            self._button(p, "📋  Copiar arquivos do disco", lambda: self.copy_disc_files(drive_var.get(), status_var), bg="#173047").pack(fill="x", pady=4)
            self._button(p, "🔄  Atualizar unidades", refresh, bg="#173047").pack(fill="x", pady=4)

        tool("♫\nExtrair Áudio", scan, True)
        tool("◉\nCopiar Disco", lambda: self.copy_disc_files(drive_var.get(), status_var))
        tool("▣\nGravar Dados", burn_data)
        tool("♪\nGravar Áudio", burn_audio)
        tool("ISO\nGravar ISO", burn_iso)
        tool("⚒\nMais Ferramentas", more_tools)

        actions = tk.Frame(body, bg=PANEL)
        actions.pack(fill="x")
        self._button(actions, "↻  Ler faixas do CD", scan, bg=GREEN2).pack(side="left", padx=(0, 6))
        self._button(actions, "♫  Extrair selecionadas", copy_selected, bg=GREEN2).pack(side="left", padx=6)
        self._button(actions, "♫  Extrair todas", lambda: (items.selection_set(0, "end"), copy_selected()), bg=BLUE).pack(side="left", padx=6)
        self._button(actions, "⏏  Ejetar Bandeja", lambda: self.eject_drive(drive_var.get(), status_var), bg="#173047").pack(side="right")

        tk.Label(body, textvariable=status_var, bg=PANEL, fg=GREEN,
                 font=("Segoe UI", 9), anchor="w").pack(fill="x", pady=(10, 0))
        refresh()


if __name__ == "__main__":
    ModernApp(tk.Tk()).root.mainloop()
