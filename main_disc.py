"""Interface adicional para discos; main_batch.py e main.py ficam intactos."""

from pathlib import Path
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from main_queue100 import App, ffmpeg_location
from disc_tools import optical_drives, media_files, audio_cd_tracks, convert_file, rip_and_convert
from desktop_shortcut import ensure_desktop_shortcut


class DiscApp(App):
    def __init__(self, root):
        super().__init__(root)
        root.title("Converte MP3 Sem Limite Evaldo — YouTube e CD/DVD")
        root.geometry("850x980")
        self.disc_running = False
        self.drive = tk.StringVar()
        self.disc_format = tk.StringVar(value="mp3")
        panel = tk.LabelFrame(root, text="Copiar CD/DVD próprio ou autorizado", padx=12, pady=8)
        panel.pack(fill="both", padx=20, pady=(0, 12))
        top = tk.Frame(panel)
        top.pack(fill="x")
        tk.Label(top, text="Unidade:").pack(side="left")
        self.drives = ttk.Combobox(top, textvariable=self.drive, width=9, state="readonly")
        self.drives.pack(side="left", padx=5)
        tk.Button(top, text="Atualizar unidades", command=self.refresh_drives).pack(side="left")
        tk.Label(top, text="Saída:").pack(side="left", padx=(20, 2))
        ttk.Combobox(top, textvariable=self.disc_format, values=("mp3", "mp4", "avi"),
                     width=7, state="readonly").pack(side="left")
        tk.Button(top, text="Ler disco", command=self.scan_disc).pack(side="left", padx=12)
        tk.Label(panel, text="CD de áudio: MP3 por faixa. CD/DVD com arquivos: MP3 (áudio), MP4 ou AVI (vídeo).",
                 anchor="w").pack(fill="x", pady=4)
        self.items = tk.Listbox(panel, height=5, selectmode="extended")
        self.items.pack(fill="both", expand=True)
        self.entries = []
        self.disc_button = tk.Button(panel, text="Copiar itens selecionados", command=self.start_disc)
        self.disc_button.pack(pady=5)
        self.refresh_drives()
        self.root.after(700, self.install_shortcut)

    def install_shortcut(self):
        def create():
            try:
                result = ensure_desktop_shortcut()
                self.root.after(0, lambda: self.report(result))
            except Exception as exc:
                self.root.after(0, lambda error=str(exc): self.report(f"Atalho: {error}"))
        threading.Thread(target=create, daemon=True).start()

    def refresh_drives(self):
        drives = optical_drives()
        self.drives["values"] = drives
        self.drive.set(drives[0] if drives else "")

    def scan_disc(self):
        if self.disc_running:
            return
        self.items.delete(0, "end")
        self.entries = []
        drive = self.drive.get()
        if not drive:
            messagebox.showwarning("CD/DVD", "Insira um disco e atualize as unidades.")
            return
        try:
            files = media_files(drive)
            if files:
                self.entries = [("file", path) for path in files[:200]]
                for path in files[:200]:
                    self.items.insert("end", str(path.relative_to(Path(drive))))
            else:
                self.entries = [("track", track) for track in audio_cd_tracks(drive)]
                for number, start, end in (item for _, item in self.entries):
                    self.items.insert("end", f"CD de áudio — faixa {number:02d} ({(end-start)//75}s)")
            if not self.entries:
                messagebox.showinfo("CD/DVD", "Não encontrei arquivos de mídia ou faixas de CD de áudio.")
        except Exception as exc:
            messagebox.showerror("CD/DVD", str(exc))

    def start_disc(self):
        if self.disc_running:
            return
        selected = [self.entries[i] for i in self.items.curselection()]
        if not selected:
            messagebox.showwarning("CD/DVD", "Selecione pelo menos um item do disco.")
            return
        folder = self.folder.get().strip()
        if not Path(folder).is_dir():
            messagebox.showwarning("Destino", "Escolha uma pasta de destino existente acima.")
            return
        fmt = self.disc_format.get()
        if selected[0][0] == "track" and fmt != "mp3":
            messagebox.showwarning("Formato", "Faixas de CD de áudio podem ser salvas em MP3.")
            return
        if not messagebox.askyesno("Permissão de uso", "Você tem direito ou autorização para copiar este conteúdo?"):
            return
        try:
            ffmpeg = ffmpeg_location()
        except Exception as exc:
            messagebox.showerror("FFmpeg", str(exc))
            return
        self.disc_running = True
        self.disc_button.config(state="disabled")
        threading.Thread(target=self.disc_worker, args=(selected, folder, fmt, ffmpeg,
                                                       self.drive.get()), daemon=True).start()

    def disc_worker(self, selected, folder, fmt, ffmpeg, drive):
        ok = 0
        for index, (kind, source) in enumerate(selected, 1):
            try:
                if kind == "track":
                    result = rip_and_convert(drive, [source], folder, ffmpeg,
                                             lambda number, status: None)
                    status = result[0][1]
                    if status != "concluído":
                        raise RuntimeError(status)
                    label = f"faixa {source[0]}"
                else:
                    # ID da fonte evita sobrescrever itens de mesmo nome em pastas diferentes.
                    label = source.name
                    destination = Path(folder) / f"Disco {drive[0]} - {source.stem}.{fmt}"
                    convert_file(source, destination, fmt, ffmpeg)
                ok += 1
                self.root.after(0, lambda x=label: self.report(f"Disco: {x} concluído."))
            except Exception as exc:
                self.root.after(0, lambda x=str(exc): self.report(f"Disco: erro: {x}"))
            self.root.after(0, lambda n=index: self.status.set(
                f"CD/DVD: {n}/{len(selected)} item(ns) processado(s)."))
        self.root.after(0, lambda: self.finish_disc(ok, len(selected)))

    def finish_disc(self, ok, total):
        self.disc_running = False
        self.disc_button.config(state="normal")
        messagebox.showinfo("CD/DVD", f"Concluído: {ok} de {total} item(ns). Veja os detalhes no painel.")


if __name__ == "__main__":
    DiscApp(tk.Tk()).root.mainloop()
