"""Instala o executável FFmpeg para Windows fornecido por imageio-ffmpeg."""
from pathlib import Path
import shutil
import imageio_ffmpeg

source = Path(imageio_ffmpeg.get_ffmpeg_exe())
destination = Path(__file__).resolve().parent / "bin" / "ffmpeg.exe"
destination.parent.mkdir(exist_ok=True)
shutil.copy2(source, destination)
print(f"FFmpeg pronto em {destination}")
