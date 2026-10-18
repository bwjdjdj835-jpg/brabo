"""Baixar vídeos e músicas do YouTube com o yt-dlp.

Aceita um link ou o nome do vídeo (pega o primeiro resultado da busca). Vídeo sai em MP4 (até 1080p) e
música em MP3, na pasta Vídeos\\Jarvis. O ffmpeg vem do pacote imageio-ffmpeg, sem instalar nada no Windows.
Baixe só o que você tem direito de baixar (seus vídeos, conteúdo liberado, uso pessoal).
"""
import logging
import os
import re

import yt_dlp

PASTA = os.path.join(os.path.expanduser("~"), "Videos", "Jarvis")
LIMITE_MINUTOS = 180  # nada de baixar lives de 10 horas por engano

log = logging.getLogger("jarvis")


def _ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        log.warning("ffmpeg indisponível: vídeo sai em qualidade menor e música sai sem converter para MP3")
        return None


def eh_link(texto):
    return bool(re.match(r"https?://(www\.|m\.|music\.)?(youtube\.com|youtu\.be)/", texto.strip()))


def buscar(busca):
    """Primeiro resultado da busca no YouTube, sem baixar. Devolve (id do vídeo, título)."""
    opcoes = {"quiet": True, "no_warnings": True, "extract_flat": "in_playlist", "noplaylist": True}
    with yt_dlp.YoutubeDL(opcoes) as ydl:
        info = ydl.extract_info(busca if eh_link(busca) else f"ytsearch1:{busca}", download=False)
    if info.get("entries") is not None:
        entradas = [e for e in info["entries"] if e]
        if not entradas:
            raise ValueError(f"Não achei nada para '{busca}'.")
        info = entradas[0]
    return info["id"], info.get("title") or busca


def baixar(alvo, audio=False, ao_progresso=None):
    """Baixa um vídeo (ou só o áudio). Devolve (caminho do arquivo, título)."""
    alvo = alvo.strip()
    if not alvo:
        raise ValueError("Diga o nome ou o link do vídeo.")
    origem = alvo if eh_link(alvo) else f"ytsearch1:{alvo}"
    ffmpeg = _ffmpeg()
    os.makedirs(PASTA, exist_ok=True)

    def progresso(estado):
        if ao_progresso and estado.get("status") == "downloading":
            total = estado.get("total_bytes") or estado.get("total_bytes_estimate")
            if total:
                ao_progresso(int(estado.get("downloaded_bytes", 0) * 100 / total))

    opcoes = {
        "outtmpl": os.path.join(PASTA, "%(title).80s.%(ext)s"),
        "windowsfilenames": True,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "progress_hooks": [progresso],
        "match_filter": yt_dlp.utils.match_filter_func(f"duration < {LIMITE_MINUTOS * 60}"),
    }
    if ffmpeg:
        opcoes["ffmpeg_location"] = ffmpeg
    if audio:
        opcoes["format"] = "bestaudio/best"
        if ffmpeg:
            opcoes["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}]
    elif ffmpeg:
        opcoes["format"] = "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/bv*[height<=1080]+ba/b[height<=1080]/b"
        opcoes["merge_output_format"] = "mp4"
    else:
        opcoes["format"] = "b[ext=mp4]/b"

    with yt_dlp.YoutubeDL(opcoes) as ydl:
        info = ydl.extract_info(origem, download=True)
        if info and info.get("entries") is not None:  # busca: vem uma lista com um resultado
            entradas = [e for e in info["entries"] if e]
            if not entradas:
                raise ValueError(f"Não achei nenhum vídeo para '{alvo}' (ou ele passa de {LIMITE_MINUTOS} minutos).")
            info = entradas[0]
        if not info or not info.get("requested_downloads"):
            raise ValueError(f"O vídeo passa de {LIMITE_MINUTOS} minutos ou não pôde ser baixado.")
        arquivo = info["requested_downloads"][0]["filepath"]
    if audio and ffmpeg:
        arquivo = os.path.splitext(arquivo)[0] + ".mp3"
    log.info("YouTube baixado: %s", arquivo)
    return arquivo, info.get("title") or os.path.basename(arquivo)
