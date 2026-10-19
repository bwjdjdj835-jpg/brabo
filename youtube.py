"""YouTube com o yt-dlp: baixar vídeos, músicas, playlists e vários vídeos de uma busca, e ler as legendas.

Aceita um link ou o nome do vídeo (pega o primeiro resultado da busca). Vídeo sai em MP4 (até 1080p) e
música em MP3, na pasta Vídeos\\Jarvis. O ffmpeg vem do pacote imageio-ffmpeg, sem instalar nada no Windows.
As legendas (inclusive as automáticas) viram texto para o Claude resumir o que os vídeos ensinam.
Baixe só o que você tem direito de baixar (seus vídeos, conteúdo liberado, uso pessoal).
"""
import difflib
import html
import logging
import os
import re
import unicodedata

import yt_dlp

PASTA = os.path.join(os.path.expanduser("~"), "Videos", "Jarvis")
LIMITE_MINUTOS = 180   # nada de baixar lives de 10 horas por engano
MAX_VIDEOS = 150       # de uma vez, numa busca
MAX_PLAYLIST = 200
PALAVRAS_VAZIAS = {"de", "do", "da", "dos", "das", "o", "a", "os", "as", "um", "uma", "e", "com", "que", "no", "na",
                   "em", "para", "pra", "sobre", "tiver", "tem", "the", "of", "and", "to", "ou", "titulo", "titilo",
                   "parecido", "parecidos", "playlist", "payliste", "playliste", "video", "videos"}

log = logging.getLogger("jarvis")


def _ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        log.warning("ffmpeg indisponível: vídeo sai em qualidade menor e música sai sem converter para MP3")
        return None


def _sem_acento(texto):
    texto = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


def _nome_pasta(texto):
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "", texto).strip(" .")[:60] or "videos"


def eh_link(texto):
    return bool(re.match(r"https?://(www\.|m\.|music\.)?(youtube\.com|youtu\.be)/", texto.strip()))


def eh_playlist(texto):
    return eh_link(texto) and bool(re.search(r"[?&]list=|/playlist\b", texto))


def _opcoes(pasta, audio, ao_progresso=None):
    ffmpeg = _ffmpeg()

    def progresso(estado):
        if ao_progresso and estado.get("status") == "downloading":
            total = estado.get("total_bytes") or estado.get("total_bytes_estimate")
            if total:
                ao_progresso(int(estado.get("downloaded_bytes", 0) * 100 / total), estado.get("info_dict") or {})

    opcoes = {
        "outtmpl": os.path.join(pasta, "%(title).80s.%(ext)s"),
        "windowsfilenames": True,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "ignoreerrors": True,  # vídeo privado ou bloqueado no meio da lista não para o resto
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
    return opcoes


def _arquivos(info, audio):
    """Caminhos baixados de um resultado (um vídeo, uma busca ou uma playlist)."""
    if not info:
        return []
    if info.get("entries") is not None:
        return [a for e in info["entries"] for a in _arquivos(e, audio)]
    arquivos = [d["filepath"] for d in info.get("requested_downloads") or [] if d.get("filepath")]
    if audio:
        arquivos = [os.path.splitext(a)[0] + ".mp3" if os.path.exists(os.path.splitext(a)[0] + ".mp3") else a
                    for a in arquivos]
    return arquivos


def _titulo_tem(titulo, palavras):
    """O título tem todas as palavras? Aceita erro de digitação ("jarves" acha "Jarvis")."""
    no_titulo = re.findall(r"\w+", _sem_acento(titulo))
    for palavra in palavras:
        if not any(palavra in t or (len(palavra) >= 4 and difflib.SequenceMatcher(None, palavra, t).ratio() >= 0.8)
                   for t in no_titulo):
            return False
    return True


def buscar(busca):
    """Primeiro resultado da busca no YouTube, sem baixar. Devolve (id do vídeo, título)."""
    resultados = listar(busca, 1)
    if not resultados:
        raise ValueError(f"Não achei nada para '{busca}'.")
    return resultados[0]["id"], resultados[0]["titulo"]


def listar(alvo, quantidade=10, so_com_titulo=False):
    """Vídeos de uma busca ou playlist, sem baixar: [{id, titulo, url, duracao}].

    so_com_titulo: só os vídeos cujo título tem todas as palavras da busca (ex.: "jarvis").
    """
    if eh_playlist(alvo):
        origem = alvo
    elif eh_link(alvo):
        origem = alvo
    else:
        # busca mais do que o pedido, porque o filtro de título e o de duração descartam alguns
        # e sem o "ruído" da frase: colchetes, "ou", "título parecido"...
        palavras = [p for p in re.findall(r"\w+", alvo) if _sem_acento(p) not in PALAVRAS_VAZIAS]
        busca = " ".join(dict.fromkeys(palavras)) or alvo
        origem = f"ytsearch{min(quantidade * (3 if so_com_titulo else 2), 400)}:{busca}"
    opcoes = {"quiet": True, "no_warnings": True, "extract_flat": "in_playlist", "ignoreerrors": True,
              "noplaylist": not eh_playlist(alvo), "playlistend": MAX_PLAYLIST}
    with yt_dlp.YoutubeDL(opcoes) as ydl:
        info = ydl.extract_info(origem, download=False) or {}
    entradas = info.get("entries") if info.get("entries") is not None else [info]
    # "jarvis ou como criar jarvis": o título pode ter qualquer uma das alternativas
    alternativas = [[p for p in re.findall(r"\w+", parte) if p not in PALAVRAS_VAZIAS]
                    for parte in re.split(r"\bou\b|\bor\b", _sem_acento(alvo))]
    alternativas = [a for a in alternativas if a]
    resultados = []
    for entrada in entradas:
        if not entrada or not entrada.get("id"):
            continue
        titulo = entrada.get("title") or ""
        if (so_com_titulo and not eh_link(alvo) and alternativas
                and not any(_titulo_tem(titulo, palavras) for palavras in alternativas)):
            continue
        if (entrada.get("duration") or 0) > LIMITE_MINUTOS * 60:
            continue
        resultados.append({"id": entrada["id"], "titulo": titulo, "duracao": entrada.get("duration"),
                           "url": entrada.get("url") or f"https://www.youtube.com/watch?v={entrada['id']}"})
        if len(resultados) >= quantidade and not eh_playlist(alvo):
            break
    return resultados


def baixar(alvo, audio=False, ao_progresso=None):
    """Baixa um vídeo (ou só o áudio). Devolve (caminho do arquivo, título)."""
    alvo = alvo.strip()
    if not alvo:
        raise ValueError("Diga o nome ou o link do vídeo.")
    os.makedirs(PASTA, exist_ok=True)
    opcoes = _opcoes(PASTA, audio, ao_progresso and (lambda pct, _info: ao_progresso(pct)))
    with yt_dlp.YoutubeDL(opcoes) as ydl:
        info = ydl.extract_info(alvo if eh_link(alvo) else f"ytsearch1:{alvo}", download=True)
    arquivos = _arquivos(info, audio)
    if not arquivos:
        raise ValueError(f"Não achei o vídeo '{alvo}', ou ele passa de {LIMITE_MINUTOS} minutos.")
    titulo = info.get("title") if not info.get("entries") else (info["entries"][0] or {}).get("title")
    log.info("YouTube baixado: %s", arquivos[0])
    return arquivos[0], titulo or os.path.basename(arquivos[0])


def baixar_varios(alvo, quantidade=10, audio=False, so_com_titulo=True, ao_progresso=None):
    """Baixa uma playlist inteira ou vários vídeos de uma busca, numa pasta com o nome da busca.

    ao_progresso(n, total, titulo, pct). Devolve (pasta, [arquivos], quantos falharam).
    """
    alvo = alvo.strip()
    if not alvo:
        raise ValueError("Diga o nome da playlist, o link ou o que buscar.")
    quantidade = max(1, min(quantidade, MAX_PLAYLIST if eh_playlist(alvo) else MAX_VIDEOS))
    videos = listar(alvo, quantidade, so_com_titulo)[:quantidade]
    if not videos:
        raise ValueError(f"Não achei vídeos para '{alvo}'" + (" com isso no título." if so_com_titulo else "."))
    nome = nome_playlist(alvo) if eh_playlist(alvo) else alvo
    pasta = os.path.join(PASTA, _nome_pasta(nome))
    os.makedirs(pasta, exist_ok=True)

    arquivos, falhas = [], 0
    for n, video in enumerate(videos, 1):
        if ao_progresso:
            ao_progresso(n, len(videos), video["titulo"], 0)
        opcoes = _opcoes(pasta, audio, ao_progresso and (
            lambda pct, _info, n=n, titulo=video["titulo"]: ao_progresso(n, len(videos), titulo, pct)))
        try:
            with yt_dlp.YoutubeDL(opcoes) as ydl:
                novos = _arquivos(ydl.extract_info(video["url"], download=True), audio)
        except Exception:
            log.warning("Falha ao baixar %s", video["url"], exc_info=True)
            novos = []
        if novos:
            arquivos += novos
        else:
            falhas += 1
    log.info("YouTube: %d baixados em %s (%d falharam)", len(arquivos), pasta, falhas)
    return pasta, arquivos, falhas


def _texto_vtt(conteudo):
    """Legenda .vtt para texto corrido, sem horários e sem as repetições das legendas automáticas."""
    linhas = conteudo.splitlines()
    texto, anterior = [], None
    for linha in linhas:
        linha = html.unescape(re.sub(r"<[^>]+>", "", linha)).strip()
        if (not linha or "-->" in linha or linha.startswith(("WEBVTT", "Kind:", "Language:", "NOTE"))
                or linha == anterior):
            continue
        texto.append(linha)
        anterior = linha
    return " ".join(texto)


def _escolher_legenda(info):
    """Uma legenda só (pedir várias faz o YouTube bloquear com erro 429).

    Ordem: legenda feita à mão em português ou inglês; senão a automática na língua original do vídeo
    (é a mais fiel); senão a automática traduzida para o português.
    """
    manuais, automaticas = info.get("subtitles") or {}, info.get("automatic_captions") or {}
    original = (info.get("language") or "").split("-")[0]
    candidatas = [manuais.get(l) for l in ("pt-BR", "pt", "en", "en-US")]
    candidatas += [automaticas.get(l) for l in (f"{original}-orig", original) if original]
    candidatas += [v for k, v in automaticas.items() if k.endswith("-orig")]
    candidatas += [automaticas.get("pt"), automaticas.get("en")]
    for formatos in candidatas:
        for formato in formatos or []:
            if formato.get("ext") == "vtt" and formato.get("url"):
                return formato["url"]
    return None


def detalhes(url, legenda=True):
    """Tudo o que dá para saber de um vídeo sem baixar: título, canal, duração, data, views, descrição e,
    se legenda=True, o texto falado (vazio se o vídeo não tiver legenda)."""
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "noplaylist": True, "noprogress": True}) as ydl:
        info = ydl.extract_info(url, download=False) or {}
        endereco = _escolher_legenda(info) if legenda else None
        texto = ""
        if endereco:
            try:
                texto = _texto_vtt(ydl.urlopen(endereco).read().decode("utf-8", "replace"))
            except Exception:
                log.warning("Não consegui a legenda de %s", url, exc_info=True)
    data = info.get("upload_date") or ""
    return {
        "titulo": info.get("title") or url,
        "url": info.get("webpage_url") or url,
        "canal": info.get("channel") or info.get("uploader") or "",
        "duracao": info.get("duration") or 0,
        "data": f"{data[6:8]}/{data[4:6]}/{data[:4]}" if len(data) == 8 else "",
        "visualizacoes": info.get("view_count"),
        "curtidas": info.get("like_count"),
        "descricao": info.get("description") or "",
        "texto": texto,
    }


def transcricao(url):
    """Texto falado no vídeo, pela legenda. Devolve (título, descrição, texto); texto vazio se não houver."""
    video = detalhes(url)
    return video["titulo"], video["descricao"][:1500], video["texto"]


def nome_playlist(url):
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "extract_flat": True, "playlistend": 1}) as ydl:
        return (ydl.extract_info(url, download=False) or {}).get("title") or "playlist"
