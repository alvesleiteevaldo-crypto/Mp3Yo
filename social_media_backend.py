"""Backend para TikTok e Facebook no FluxMídia.

Integração inspirada no projeto MIT:
https://github.com/nayandas69/Social-Media-Downloader
Autor original: Nayan Das.
O fluxo abaixo mantém a ideia do projeto: URLs públicas processadas com yt-dlp
e FFmpeg, adaptadas para a interface gráfica do FluxMídia.
"""

from pathlib import Path
from urllib.parse import urlparse
import yt_dlp


SOCIAL_DOMAINS = {
    "tiktok.com", "www.tiktok.com", "m.tiktok.com", "vm.tiktok.com", "vt.tiktok.com",
    "facebook.com", "www.facebook.com", "m.facebook.com", "mbasic.facebook.com",
    "fb.watch", "www.fb.watch",
}


def is_social_url(url):
    try:
        host = (urlparse(url).hostname or "").lower()
        return host in SOCIAL_DOMAINS
    except ValueError:
        return False


def platform_name(url):
    host = (urlparse(url).hostname or "").lower()
    if "tiktok" in host:
        return "TikTok"
    if "facebook" in host or host.endswith("fb.watch"):
        return "Facebook"
    return "Social"


def download_media(url, folder, output_type, mp3_quality, ffmpeg, progress_hook, stop_check=None):
    """Baixa mídia pública TikTok/Facebook usando o fluxo do Social-Media-Downloader."""

    def hook(data):
        if stop_check and stop_check():
            raise RuntimeError("Conversão interrompida pelo usuário.")
        progress_hook(data)

    options = {
        "noplaylist": True,
        "outtmpl": str(Path(folder) / "%(title).180B [%(id)s].%(ext)s"),
        "ffmpeg_location": ffmpeg,
        "progress_hooks": [hook],
        "quiet": True,
        "no_warnings": True,
        "retries": 3,
        "fragment_retries": 3,
    }

    if output_type == "Áudio MP3":
        options.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": str(mp3_quality),
            }],
        })
    elif output_type.startswith("Vídeo "):
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
        raise ValueError("Formato de saída não suportado pelo módulo social.")

    with yt_dlp.YoutubeDL(options) as ydl:
        result = ydl.download([url])
        if result:
            raise RuntimeError(f"O extrator social retornou código {result}.")
