"""Leitura de CDs de áudio e arquivos de CD/DVD no Windows, sem remover proteção."""

import ctypes
from ctypes import wintypes
from pathlib import Path
import os
import subprocess
import tempfile
import wave


MEDIA_EXTENSIONS = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg",
                    ".mp4", ".avi", ".mov", ".mkv", ".mpeg", ".mpg", ".vob"}
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".mpeg", ".mpg", ".vob"}


def optical_drives():
    if os.name != "nt":
        return []
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetDriveTypeW.argtypes = (wintypes.LPCWSTR,)
    kernel.GetDriveTypeW.restype = wintypes.UINT
    return [f"{chr(letter)}:\\" for letter in range(ord("A"), ord("Z") + 1)
            if kernel.GetDriveTypeW(f"{chr(letter)}:\\") == 5]


def media_files(drive):
    root = Path(drive)
    if drive not in optical_drives():
        raise ValueError("Selecione uma unidade de CD/DVD detectada pelo Windows.")
    try:
        return sorted((p for p in root.rglob("*") if p.is_file()
                       and p.suffix.lower() in MEDIA_EXTENSIONS), key=str)
    except OSError as exc:
        raise RuntimeError(f"Não foi possível ler o disco: {exc}") from exc


def audio_cd_tracks(drive):
    """Consulta a tabela de faixas de um CD de áudio pelo driver do Windows."""
    if os.name != "nt" or drive not in optical_drives():
        raise ValueError("Selecione uma unidade óptica do Windows.")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                   ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                                   wintypes.HANDLE)
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.DeviceIoControl.argtypes = (wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p,
                                       wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                                       ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p)
    kernel.DeviceIoControl.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel.CreateFileW("\\\\.\\" + drive[0] + ":", 0x80000000, 3,
                                None, 3, 0, None)
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        toc = ctypes.create_string_buffer(804)
        returned = wintypes.DWORD()
        if not kernel.DeviceIoControl(handle, 0x24000, None, 0, toc, len(toc),
                                      ctypes.byref(returned), None):
            raise ctypes.WinError(ctypes.get_last_error())
        raw = toc.raw
        first, last = raw[2], raw[3]
        if last < first or last > 99 or returned.value < 4 + (last-first+2)*8:
            raise RuntimeError("Tabela de faixas inválida ou CD ausente.")
        positions = []
        for index in range(last-first+2):
            entry = raw[4+8*index:12+8*index]
            msf = entry[5:8]
            lba = (msf[0]*60 + msf[1])*75 + msf[2] - 150
            positions.append((entry[1] & 4, max(0, lba)))
        return [(first+i, positions[i][1], positions[i+1][1])
                for i in range(last-first+1)
                if not positions[i][0] and positions[i+1][1] > positions[i][1]]
    finally:
        kernel.CloseHandle(handle)


def rip_audio_track(drive, start, end, wave_path, on_progress=None):
    """Lê CDDA PCM 44,1 kHz estéreo; falhas de leitura encerram a faixa."""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                   ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                                   wintypes.HANDLE)
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.DeviceIoControl.argtypes = (wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p,
                                       wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                                       ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p)
    kernel.DeviceIoControl.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel.CreateFileW("\\\\.\\" + drive[0] + ":", 0x80000000, 3,
                                None, 3, 0, None)
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        with wave.open(str(wave_path), "wb") as wav:
            wav.setnchannels(2)
            wav.setsampwidth(2)
            wav.setframerate(44100)
            for sector in range(start, end, 16):
                count = min(16, end-sector)
                # RAW_READ_INFO: LARGE_INTEGER DiskOffset, ULONG SectorCount, enum CDDA=2.
                raw_info = ctypes.create_string_buffer(16)
                ctypes.memmove(raw_info, (sector*2048).to_bytes(8,"little") +
                               count.to_bytes(4,"little") + (2).to_bytes(4,"little"), 16)
                output = ctypes.create_string_buffer(count*2352)
                returned = wintypes.DWORD()
                if not kernel.DeviceIoControl(handle, 0x2403e, raw_info, 16, output,
                                              len(output), ctypes.byref(returned), None):
                    raise ctypes.WinError(ctypes.get_last_error())
                if returned.value != len(output):
                    raise RuntimeError("Leitura incompleta da faixa do CD.")
                wav.writeframesraw(output.raw)
                if on_progress:
                    on_progress(sector-start+count, end-start)
    finally:
        kernel.CloseHandle(handle)


def convert_file(source, destination, output_format, ffmpeg):
    if output_format not in {"mp3", "mp4", "avi"}:
        raise ValueError("Formato inválido.")
    if output_format != "mp3" and source.suffix.lower() not in VIDEO_EXTENSIONS:
        raise ValueError("MP4 e AVI requerem um arquivo de vídeo; para áudio escolha MP3.")
    if destination.exists():
        raise FileExistsError(f"Arquivo já existe: {destination.name}")
    args = [ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-n", "-i", str(source)]
    if output_format == "mp3":
        args += ["-vn", "-codec:a", "libmp3lame", "-b:a", "192k"]
    elif output_format == "mp4":
        args += ["-map", "0:v:0", "-map", "0:a?", "-c:v", "libx264", "-crf", "20",
                 "-preset", "medium", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]
    else:
        args += ["-map", "0:v:0", "-map", "0:a?", "-c:v", "mpeg4", "-q:v", "3",
                 "-c:a", "libmp3lame", "-b:a", "192k"]
    args.append(str(destination))
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode:
        destination.unlink(missing_ok=True)
        raise RuntimeError(result.stderr.strip()[-500:] or "Falha ao converter mídia.")


def rip_and_convert(drive, tracks, folder, ffmpeg, on_update):
    results = []
    for number, start, end in tracks:
        dest = Path(folder) / f"CD {drive[0]} - faixa {number:02d}.mp3"
        if dest.exists():
            results.append((number, "já existe"))
            continue
        try:
            with tempfile.TemporaryDirectory() as tmp:
                wav = Path(tmp) / "faixa.wav"
                rip_audio_track(drive, start, end, wav)
                convert_file(wav, dest, "mp3", ffmpeg)
            results.append((number, "concluído"))
        except Exception as exc:
            results.append((number, f"erro: {exc}"))
        on_update(number, results[-1][1])
    return results
