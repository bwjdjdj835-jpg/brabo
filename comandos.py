"""Comandos que o Jarvis sabe executar.

Para ensinar um site ou programa novo, é só adicionar uma linha em SITES ou PROGRAMAS.
A chave é como você fala (sem acento, minúsculo); o valor é (como ele responde, o que abre).
"""
import ctypes
import datetime
import random
import re
import subprocess
import unicodedata
import urllib.parse
import webbrowser

import psutil

SITES = {
    "youtube": ("o YouTube", "https://www.youtube.com"),
    "google": ("o Google", "https://www.google.com"),
    "gmail": ("o Gmail", "https://mail.google.com"),
    "whatsapp": ("o WhatsApp", "https://web.whatsapp.com"),
    "instagram": ("o Instagram", "https://www.instagram.com"),
    "facebook": ("o Facebook", "https://www.facebook.com"),
    "tiktok": ("o TikTok", "https://www.tiktok.com"),
    "twitter": ("o X", "https://x.com"),
    "netflix": ("a Netflix", "https://www.netflix.com"),
    "twitch": ("a Twitch", "https://www.twitch.tv"),
    "github": ("o GitHub", "https://github.com"),
    "claude": ("o Claude", "https://claude.ai"),
    "maps": ("o Google Maps", "https://maps.google.com"),
    "mapa": ("o Google Maps", "https://maps.google.com"),
}

PROGRAMAS = {
    "calculadora": ("a calculadora", "calc"),
    "bloco de notas": ("o bloco de notas", "notepad"),
    "explorador": ("o explorador de arquivos", "explorer"),
    "arquivos": ("o explorador de arquivos", "explorer"),
    "pasta": ("o explorador de arquivos", "explorer"),
    "chrome": ("o Chrome", "chrome"),
    "edge": ("o Edge", "msedge"),
    "navegador": ("o navegador", "https://www.google.com"),
    "spotify": ("o Spotify", "spotify:"),
    "discord": ("o Discord", "discord:"),
    "steam": ("a Steam", "steam:"),
    "configurac": ("as configurações", "ms-settings:"),
    "paint": ("o Paint", "mspaint"),
    "terminal": ("o terminal", "cmd"),
    "prompt": ("o terminal", "cmd"),
    "vs code": ("o VS Code", "code"),
    "word": ("o Word", "winword"),
    "excel": ("o Excel", "excel"),
    "powerpoint": ("o PowerPoint", "powerpnt"),
    "camera": ("a câmera", "microsoft.windows.camera:"),
    "loja": ("a Microsoft Store", "ms-windows-store:"),
}

DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]

PIADAS = [
    "Por que o computador foi ao médico? Porque estava com um vírus.",
    "Qual é o café mais perigoso do mundo? O ex-presso.",
    "O que o zero disse para o oito? Que cinto bonito!",
    "Por que a planta não responde? Porque ela é muda.",
    "O que o pato disse para a pata? Vem quá!",
    "Por que o livro de matemática estava triste? Porque tinha muitos problemas.",
]

AJUDA = (
    "Eu sei abrir sites e programas, pesquisar no Google e no YouTube, tocar músicas, "
    "dizer as horas e a data, controlar o volume e mostrar o status do sistema. "
    "Com o Claude, eu crio apps e sites para o senhor e respondo qualquer pergunta. "
    "Também junto até 100 arquivos em um PDF e baixo vídeos e músicas do YouTube. "
    "Faço lembretes e timers, como: me lembra em 10 minutos de tirar o bolo, e tenho o modo foco, "
    "que lembra o senhor de beber água. "
    "É só dizer, por exemplo: Jarvis, cria um site de portfólio."
)

VERBOS_BUSCA = r"\b(?:pesquis\w*|procur\w*|busc\w*|googl\w*)\b"

TECLA_MUDO, TECLA_MENOS, TECLA_MAIS = 0xAD, 0xAE, 0xAF
TECLA_PROXIMA, TECLA_ANTERIOR, TECLA_PLAY = 0xB0, 0xB1, 0xB3


_PALAVRAS_YOUTUBE = (
    # a quantidade sai primeiro, enquanto ainda vem antes de "vídeos"
    r"(?:\d{1,3}|um|uma|dois|duas|tres|quatro|cinco|seis|sete|oito|nove|dez|quinze|vinte|trinta|quarenta|cinquenta)"
    r"(?= (?:videos?|musicas?|audios?|clipes?|primeiros?)\b)",
    r"baix\w*", r"download\w*", r"resum\w*", r"estud\w*", r"assist\w*", r"aprend\w*", r"(?:pra|para) mim",
    r"(?:do|no|o) youtube", "youtube", r"em mp[34]", r"mp[34]", "todos os", "todas as", "todos", "todas",
    r"(?:os|uns|alguns|varios|varias) ", r"(?:o|um|os) videos?", r"videos?", r"(?:a|uma|as) musicas?", r"musicas?",
    r"(?:o|os) audios?", r"audios?", r"(?:o|os) clipes?", r"clipes?", r"(?:a|essa|esta|da) playlists?", r"playlists?",
    r"que (?:tiver|tenham?|falam?|fala) (?:de |do |da |sobre )?", r"com (?:o nome|o titulo|nome|titulo)",
    r"no titulo", r"(?:do|da|de|dos|das|sobre)(?=\s)", "pode", "por favor", r"(?:os )?primeiros?",
)
_NUMEROS = {"um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6, "sete": 7,
            "oito": 8, "nove": 9, "dez": 10, "quinze": 15, "vinte": 20, "trinta": 30, "quarenta": 40, "cinquenta": 50}


_NUMEROS_TEMPO = {**_NUMEROS, "onze": 11, "doze": 12, "treze": 13, "catorze": 14, "quatorze": 14,
                  "dezesseis": 16, "dezessete": 17, "dezoito": 18, "dezenove": 19}
_NUM_TEMPO = r"\d{1,4}|" + "|".join(sorted(_NUMEROS_TEMPO, key=len, reverse=True))
_DURACAO = (rf"(?:\b(?:{_NUM_TEMPO})\s*(?:segundos?|seg|minutos?|min|horas?|h)\b(?:\s+e\s+meia\b)?"
            r"|\bmeia hora\b)")
_HORARIO = (rf"\b(?:as|pras)\s+({_NUM_TEMPO})(?:(?::|h)(\d{{2}})|\s*(?:h|horas?)(?:\s+e\s+(\d{{1,2}}))?)?"
            r"(?:\s+(?:minutos?\s+)?(?:da|de)\s+(manha|tarde|noite|madrugada))?\b")
_PEDE_AVISO = r"\b(?:me |nos )?(?:lembr\w*|avis\w*|acord\w*|despert\w*)\b"


def _numero(palavra):
    return int(palavra) if palavra.isdigit() else _NUMEROS_TEMPO.get(palavra, 0)


def _duracao(t):
    """Segundos de um trecho como "10 minutos", "uma hora e meia", "meia hora". 0 se não tiver."""
    total = 0
    for trecho in re.finditer(_DURACAO, t):
        pedaco = trecho.group()
        if pedaco.startswith("meia"):
            total += 1800
            continue
        numero, unidade = re.match(rf"({_NUM_TEMPO})\s*([a-z]+)", pedaco).groups()
        total += _numero(numero) * (3600 if unidade.startswith("h") else 60 if unidade.startswith("min") else 1)
        if pedaco.endswith("meia"):
            total += 1800
    return total


def _ate_horario(t):
    """"às 15:30", "às 3 da tarde": devolve (segundos até lá, "15:30"), ou (0, "")."""
    achado = re.search(_HORARIO, t)
    if not achado:
        return 0, ""
    hora = _numero(achado.group(1))
    minuto = int(achado.group(2) or achado.group(3) or 0)
    periodo = achado.group(4)
    if periodo in ("tarde", "noite") and hora < 12:
        hora += 12
    if hora > 23 or minuto > 59:
        return 0, ""
    agora = datetime.datetime.now()
    alvo = agora.replace(hour=hora, minute=minuto, second=0, microsecond=0)
    acordar = re.search(r"\b(?:acord\w*|despert\w*)\b", t)
    if alvo <= agora and not periodo and not acordar and hora < 12 and alvo + datetime.timedelta(hours=12) > agora:
        alvo += datetime.timedelta(hours=12)  # "às 3" depois do almoço = 15h
    if alvo <= agora:
        alvo += datetime.timedelta(days=1)
    return (alvo - agora).total_seconds(), alvo.strftime("%H:%M")


def tempo_falado(segundos):
    h, resto = divmod(int(round(segundos)), 3600)
    m, s = divmod(resto, 60)
    partes = []
    if h:
        partes.append(f"{h} hora" + ("s" if h > 1 else ""))
    if m:
        partes.append(f"{m} minuto" + ("s" if m > 1 else ""))
    if s and not h:
        partes.append(f"{s} segundo" + ("s" if s > 1 else ""))
    return " e ".join(partes) or "instantes"


def _lembrete(t, original):
    """Lembrete, timer ou modo foco. Devolve a ação, uma resposta, ou None se a frase não é disso."""
    def tem(*padroes):
        return any(re.search(rf"\b{p}\b", t) for p in padroes)

    if tem("modo foco", "modo de foco", "modo concentracao"):
        if re.search(r"\b(?:deslig\w*|desativ\w*|encerr\w*|termin\w*|cancel\w*)\b|\bsai\w* do modo|\bpar[ae] o modo", t):
            return {"acao": "foco", "ligar": False}
        cada = re.search(r"\ba cada (.+?)(?=\b(?:por|durante)\b|$)", t)
        por = re.search(r"\b(?:por|durante)\s+(.+?)(?=\ba cada\b|$)", t)
        return {"acao": "foco", "ligar": True,
                "intervalo": max((_duracao(cada.group(1)) if cada else 0) or 1800, 60),
                "duracao": _duracao(por.group(1)) if por else 0}

    eh_timer = tem("timer", "temporizador", r"cronometr\w*", "alarme")
    if tem(r"lembretes?", "timers?", "temporizador", "alarmes?") and tem(r"cancel\w*", r"apag\w*", r"remov\w*", r"desliga\w*", r"tira\w*"):
        return {"acao": "lembretes_cancelar"}
    if tem(r"lembretes", "timers", "alarmes") or (tem("lembrete", "timer", "alarme") and tem("quais", "quantos", "tenho", "algum")):
        return {"acao": "lembretes_listar"}
    if not (eh_timer or re.search(_PEDE_AVISO, t)):
        return None

    segundos, horario = _ate_horario(t)
    prefixo = r"(?:\b(?:em|daqui a|daqui|dentro de|depois de|de|por)\s+)?"
    if not segundos and (eh_timer or re.search(rf"\b(?:em|daqui|dentro de|depois de)\s+(?:a\s+)?{_DURACAO}", t)):
        segundos = _duracao(t)
    if not segundos:
        if re.match(r"(?:pode\s+)?me\s+lembr", t):
            return "Quando, senhor? Diga, por exemplo: me lembra em 10 minutos de tirar o bolo do forno."
        return None

    resto = t
    for padrao in (_HORARIO, prefixo + _DURACAO, _PEDE_AVISO,
                   r"\b(?:um |o )?(?:timer|temporizador|alarme|cronometr\w*)\b", r"\b(?:pode|por favor|coloca|poe|bota)\b"):
        resto = re.sub(padrao, " ", resto)
    resto = re.sub(r"^(?:(?:de|do|da|que|para|pra|pro|sobre|e)\s+)+", "", " ".join(resto.split()))
    resto = re.sub(r"\s+(?:e|de|que)$", "", resto)
    texto = _com_acentos(resto, t, original) if len(resto) > 2 else ""
    quando = f"às {horario}" if horario else f"daqui a {tempo_falado(segundos)}"
    return {"acao": "lembrete", "segundos": segundos, "texto": texto, "timer": eh_timer and not texto, "quando": quando}


def _quantidade(t, padrao):
    """Quantos vídeos a frase pede ("baixa 5 vídeos", "resume três vídeos"); senão o padrão."""
    numero = re.search(r"\b(\d{1,3})\s+(?:videos?|musicas?|audios?|clipes?|primeiros?)\b", t)
    if numero:
        return int(numero.group(1))
    palavra = re.search(r"\b(" + "|".join(_NUMEROS) + r")\s+(?:videos?|musicas?|audios?|clipes?|primeiros?)\b", t)
    return _NUMEROS[palavra.group(1)] if palavra else padrao


def _pede_criacao(t):
    """Verdadeiro se a frase pede para criar ou montar algum app, site, jogo ou APK."""
    verbo = r"\b(cria|criar|crie|faz|faca|fazer|monta|montar|gera|gerar|desenvolv\w*|constro\w*|construir|compila\w*|program\w*)\b"
    alvo = r"\b(apk|aab|app|aplicativo|site|pagina|jogo|dashboard|projeto|web ?app|android|landing)\b"
    return bool(re.search(verbo, t) and re.search(alvo, t))


def normalizar(texto):
    sem_acento = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in sem_acento if unicodedata.category(c) != "Mn").strip()


def _tecla(codigo, vezes=1):
    for _ in range(vezes):
        ctypes.windll.user32.keybd_event(codigo, 0, 0, 0)
        ctypes.windll.user32.keybd_event(codigo, 0, 2, 0)


def _abrir(alvo):
    if alvo.startswith("http"):
        webbrowser.open(alvo)
    else:
        subprocess.Popen(f'start "" "{alvo}"', shell=True, creationflags=subprocess.CREATE_NO_WINDOW)


def _limpar(texto, *remover):
    for palavra in remover:
        texto = re.sub(rf"\b{palavra}\b", " ", texto)
    texto = re.sub(r"^\s*(por|sobre|de|o|a)\s+", "", re.sub(r"\s+", " ", texto))
    return texto.strip(" ,.?!")


def _com_acentos(busca, t, original):
    """Devolve o trecho como foi falado, com acentos."""
    inicio = t.find(busca)
    if inicio >= 0 and len(original) == len(t):
        return original[inicio:inicio + len(busca)]
    return busca


def _horas():
    agora = datetime.datetime.now()
    h, m = agora.hour, agora.minute
    inicio = "É 1 hora" if h == 1 else f"São {h} horas"
    if m == 0:
        return f"{inicio} em ponto."
    return f"{inicio} e {m} {'minuto' if m == 1 else 'minutos'}."


def _data():
    hoje = datetime.date.today()
    return f"Hoje é {DIAS[hoje.weekday()]}, {hoje.day} de {MESES[hoje.month - 1]} de {hoje.year}."


def _status():
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory().percent
    bateria = psutil.sensors_battery()
    texto = f"O processador está em {cpu:.0f} por cento, a memória em {ram:.0f} por cento"
    if bateria:
        texto += f" e a bateria em {bateria.percent:.0f} por cento"
        texto += ", carregando." if bateria.power_plugged else "."
    else:
        texto += "."
    return texto


def executar(comando):
    """Recebe o que você falou e devolve o que o Jarvis vai responder."""
    original = comando.lower().strip().strip(" ,.!?")
    t = normalizar(comando).strip(" ,.!?")

    def tem(*padroes):
        return any(re.search(rf"\b{p}\b", t) for p in padroes)

    def busca_de(trecho, *remover):
        return _com_acentos(_limpar(trecho, *remover), t, original)

    if not t:
        return "Pois não, senhor?"

    if re.fullmatch(r"(oi|ola|e ai|bom dia|boa tarde|boa noite)", t):
        return "Olá, senhor. Em que posso ajudar?"

    # ----- comandos criados por você (meus_comandos.json): têm prioridade sobre os padrões -----
    import comandos_usuario
    resposta_usuario = comandos_usuario.tentar(t)
    if resposta_usuario is not None:
        return resposta_usuario

    # ----- abas da interface -----
    if tem("aba", "abas", "guia", "guias") and tem(r"fech\w*", r"tira\w*", r"some\w*", r"sai\w*"):
        return {"acao": "fechar_aba", "todas": tem("todas", "tudo")}

    # ----- lembretes, timer e modo foco (antes do YouTube: "me lembra de assistir o vídeo...") -----
    lembrete = _lembrete(t, original)
    if lembrete is not None:
        return lembrete

    # ----- YouTube: baixar vídeo ou música (antes dos links, senão o link iria para a biblioteca) -----
    link_youtube = re.search(r"https?://(?:www\.|m\.|music\.)?(?:youtube\.com|youtu\.be)/[^\s<>\"]+", comando)
    sobre_videos = link_youtube or tem("video", "videos", "youtube", "musica", "musicas", "audio", "audios", "mp3",
                                       "clipe", "clipes", "playlist", "playlists")
    if sobre_videos and tem(r"relatori\w*", "pdf", r"document\w*", "docs", "drive"):
        alvo = link_youtube.group().rstrip(".,;)!?") if link_youtube else busca_de(
            t, r"^(?:pode |por favor )?(?:faz|faca|gera|cria|monta|manda|envia|coloca|poe|bota)\w*", r"(?:um|o) relatorio", r"relatori\w*", r"(?:um|o|em) pdf", "pdf",
            r"(?:um|o) documento", r"document\w*", "google docs", "docs", r"(?:no|pro|para o) google drive",
            r"(?:no|pro) drive", "drive", "com tudo", "tudo", *_PALAVRAS_YOUTUBE)
        return {"acao": "youtube_relatorio", "busca": alvo, "quantidade": _quantidade(t, None)}
    if sobre_videos and tem(r"resum\w*", r"estud\w*", r"assist\w*", r"aprend\w*") and not tem(r"baix\w*"):
        alvo = link_youtube.group().rstrip(".,;)!?") if link_youtube else busca_de(t, *_PALAVRAS_YOUTUBE)
        return {"acao": "youtube_resumir", "busca": alvo, "quantidade": _quantidade(t, 5)}
    if tem(r"baix\w*", r"download\w*") and sobre_videos:
        audio = tem("musica", "musicas", "audio", "audios", "mp3")
        alvo = link_youtube.group().rstrip(".,;)!?") if link_youtube else busca_de(t, *_PALAVRAS_YOUTUBE)
        playlist = bool(link_youtube and re.search(r"[?&]list=|/playlist", alvo)) or tem("playlist", "playlists")
        varios = (playlist or tem("todos", "todas", "varios", "varias", "videos", "musicas", "audios", "clipes")
                  or _quantidade(t, None) is not None)
        if varios and not (link_youtube and not playlist):
            return {"acao": "youtube_baixar_varios", "alvo": alvo, "audio": audio,
                    "quantidade": _quantidade(t, 200 if playlist else (150 if tem("todos", "todas") else 20))}
        return {"acao": "youtube_baixar", "alvo": alvo, "audio": audio}

    # ----- o Jarvis se atualiza: o Claude Code mexe no código dele (sempre com confirmação) -----
    if (re.search(r"\b(se|te)\s+(atualiz\w*|melhor\w*|aprimor\w*|program\w*)\b", t)
            or tem("atualiza voce", "atualize voce", "seu proprio codigo", r"autoatualiz\w*",
                   r"aplic\w* as ideias", r"us\w* as ideias", "atualiza com as ideias")):
        return {"acao": "autoatualizar", "pedido": original}

    # ----- modo tela: o Jarvis vê a tela e age nela (clicar, digitar, rolar) -----
    gatilho_tela = re.search(
        r"\b(ve|vê|veja|olha|olhe|controla|controle|assume|assuma|usa|use)\s+(a\s+|na\s+|minha\s+)?tela\b"
        r"|\bmodo\s+tela\b|\bna\s+tela\b|\bclica\w*\b|\bclique\b|faz voce mesmo|faca voce mesmo", t)
    if gatilho_tela:
        tarefa = re.sub(r"^(jarvis[,\s]+)?(ve|vê|veja|olha|olhe|controla|controle|assume|usa|use|no|em)\s+(a\s+|na\s+|minha\s+|modo\s+)?tela[,:\s]*(e\s+)?", "", original, flags=re.I).strip()
        return {"acao": "modo_tela", "tarefa": tarefa or original}

    # ----- PDF: juntar arquivos em um PDF (antes de "criar app", senão "gera o pdf do projeto" viraria app) -----
    if (len(t.split()) <= 15 and "http" not in t and tem("pdf", "pdfs", "pedefe", "pe de efe")
            and not tem("app", "aplicativo", "site", "apk", "sistema", "ferramenta")):
        if tem("biblioteca"):
            return {"acao": "pdf_biblioteca"}
        # "Jarvis" no fim da frase é tirado antes de chegar aqui, então "projeto" sozinho já vale
        if tem(r"jarv\w*", "projeto", "seu codigo", "teu codigo", "seus arquivos", "voce mesmo", "seu projeto"):
            return {"acao": "pdf_jarvis"}
        return {"acao": "pdf_escolher"}

    # Pedido longo de criar app (um prompt colado): vai direto para o Claude, sem ser confundido com outros comandos
    if _pede_criacao(t) and len(t.split()) > 12:
        return {"acao": "criar_app", "pedido": original,
                "tipo": "android" if re.search(r"\b(apk|aab|android)\b", t) else "web"}

    # ----- e-mail: só frases curtas que começam com a ordem de e-mail -----
    if (not _pede_criacao(t) and len(t.split()) <= 25
            and re.match(r"^(?:pode\s+|por favor\s+)?(?:manda|envia|enviar|mandar|escreve|escrever|configura|configure|arruma)\b", t)
            and tem("email", "e-mail", "imeiu")):
        if tem(r"configur\w*", "arruma", "ajusta", "senha") and not tem(r"mand\w*", r"envi\w*", "escreve"):
            return {"acao": "config_email"}
        return {"acao": "email", "texto": original}

    # ----- engenharia reversa: entender como algo foi feito -----
    engenharia_reversa = (tem(r"engenharia", r"engenhar\w*", "codigo fonte", "codigo-fonte", "como funciona por dentro")
                          or (tem("como") and tem(r"feit\w*", r"constru\w*", r"desenvolv\w*", r"criad\w*")))
    link = re.search(r"https?://[^\s<>\"]+", comando)
    if engenharia_reversa and link:
        return {"acao": "engenharia_site", "url": link.group().rstrip(".,;)!?")}
    if engenharia_reversa and (tem("site", "pagina", "web") and not tem("apk", "aplicativo android")):
        return {"acao": "perguntar", "texto": "Qual o endereço do site que o senhor quer que eu analise?"}
    if engenharia_reversa and tem("apk", "aplicativo", "app android", "android"):
        nome = re.search(r"\b(?:do|da|desse|dessa|deste|desta|o|a)\s+(?:apk|aplicativo|app)\s+(?:de\s+|do\s+|da\s+)?([\w-]+)", t)
        return {"acao": "engenharia_apk", "alvo": nome.group(1) if nome else ""}

    # ----- modo fundo: o Jarvis vira a tela de fundo da área de trabalho -----
    if tem(r"fundo") and tem("modo", "tela", "papel", "area"):
        return {"acao": "modo_fundo", "ligar": not tem(r"desliga\w*", r"sai\w*", r"tira\w*", "normal", r"desativ\w*", r"volta\w*")}

    # ----- biblioteca: links, arquivos e meus dados -----
    if link:
        url = link.group().rstrip(".,;)!?")
        if tem(r"abr\w*") and not tem(r"analis\w*", r"guard\w*", r"salv\w*", r"estud\w*"):
            _abrir(url)
            return "Abrindo o link."
        return {"acao": "biblioteca_link", "url": url}
    if (tem("meus dados", "minhas informacoes", "meu perfil", "dados da empresa")
            and tem(r"abr\w*", r"edit\w*", r"preench\w*", "mostra", r"atualiz\w*")):
        return {"acao": "abrir_meus_dados"}
    if tem("biblioteca", "bibliotecas") and tem(r"apag\w*", r"remov\w*", r"tira\w*", r"exclu\w*", r"delet\w*"):
        return {"acao": "biblioteca_apagar", "texto": original}
    if tem("biblioteca") and tem(r"abr\w*", "pasta"):
        return {"acao": "abrir_biblioteca"}
    if tem("biblioteca") and tem("o que tem", "quantos", "quantas", "lista", "mostra", "itens"):
        return {"acao": "biblioteca_resumo"}

    # ----- Claude Code: criar e alterar apps -----
    projeto = (r"(app|apps|aplicativo|site|pagina|landing page|web ?app|projeto|jogo|sistema|dashboard|painel"
               r"|ferramenta|apk|extensao)")
    android = bool(re.search(r"\b(apk|android|android studio|celular|play store)\b", t))
    if (re.search(r"\b(onde|que pasta|qual pasta|caminho|qual local|em que lugar)\b", t)
            and re.search(rf"\b({projeto[1:-1]}|aab|arquivo|pasta)\b", t)):
        return {"acao": "onde_ultimo", "android": bool(re.search(r"\b(apk|aab|android)\b", t))}
    if re.search(rf"\b(ultimo|ultima)\s+{projeto}\b", t):
        if tem(r"abr\w*", "mostra", "ver"):
            return {"acao": "abrir_ultimo"}
        return {"acao": "editar_app", "pedido": original}
    if re.search(rf"\b(cria|criar|crie|faz|faca|fazer|monta|montar|gera|gerar|desenvolv\w*|constro\w*|construir|programa)\b"
                 rf"\s+(?:\w+\s+){{0,3}}?{projeto}\b", t):
        return {"acao": "criar_app", "pedido": original, "tipo": "android" if android else "web"}

    # ----- energia: só com ordem direta, nunca no meio de outra frase -----
    ordem = r"^(?:jarvis\s+)?(?:pode\s+|por favor\s+)?"
    alvo = r"\s+(?:o |a |meu |minha )?(?:pc|computador|notebook|maquina|tela)(?:\s+por favor)?$"
    if re.fullmatch(r"(?:pode\s+)?cancel\w*\s+(?:o\s+)?(?:deslig\w*|reinici\w*)", t):
        subprocess.run(["shutdown", "/a"], creationflags=subprocess.CREATE_NO_WINDOW)
        return "Desligamento cancelado."
    if re.fullmatch(rf"{ordem}deslig\w*{alvo}", t):
        subprocess.run(["shutdown", "/s", "/t", "60"], creationflags=subprocess.CREATE_NO_WINDOW)
        return "Desligando o computador em 60 segundos. Diga cancelar desligamento se mudar de ideia."
    if re.fullmatch(rf"{ordem}reinici\w*{alvo}", t):
        subprocess.run(["shutdown", "/r", "/t", "60"], creationflags=subprocess.CREATE_NO_WINDOW)
        return "Reiniciando o computador em 60 segundos. Diga cancelar desligamento se mudar de ideia."
    if re.fullmatch(rf"{ordem}(?:bloque\w*|trav\w*){alvo}", t):
        ctypes.windll.user32.LockWorkStation()
        return "Bloqueando o computador."

    # ----- música e volume -----
    if tem(r"proxim\w*", "pula", "pular") and tem("musica", "faixa", "video"):
        _tecla(TECLA_PROXIMA)
        return "Próxima."
    if tem("anterior") and tem("musica", "faixa", "video"):
        _tecla(TECLA_ANTERIOR)
        return "Voltando."
    if tem(r"paus\w*", r"despaus\w*", "play", "continua", "continuar", "retoma"):
        _tecla(TECLA_PLAY)
        return "Feito."
    if tem("volume", "som"):
        if tem(r"aument\w*", "sobe", "subir", "mais", "alto"):
            _tecla(TECLA_MAIS, 5)
            return "Aumentando o volume."
        if tem(r"diminu\w*", r"abaix\w*", "baixa", "menos"):
            _tecla(TECLA_MENOS, 5)
            return "Diminuindo o volume."
        if tem("muta", "mutar", "mudo", r"silenci\w*", "tira", r"deslig\w*", "liga", "volta"):
            _tecla(TECLA_MUDO)
            return "Feito."
        return "Diga aumentar, diminuir ou silenciar o volume."

    # ----- hora e data -----
    if tem("horas", "hora", "horario"):
        return _horas()
    if tem("data") or (tem("dia") and tem("hoje", "que", "qual")):
        return _data()

    # ----- YouTube e Google -----
    if "youtube" in t and re.search(VERBOS_BUSCA, t):
        busca = busca_de(re.split(VERBOS_BUSCA, t, maxsplit=1)[1], "no youtube", "youtube")
        if busca:
            _abrir("https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(busca))
            return f"Pesquisando {busca} no YouTube."
    tocar = re.search(r"\b(?:toca|tocar|toque|coloca|bota|reproduz\w*)\s+(.+)", t)
    if tocar:
        no_navegador = tem("navegador", "chrome", "edge")
        busca = busca_de(tocar.group(1), "no youtube", "uma musica", "musica", "um video", "video",
                         "no navegador", "no chrome", "no edge", "aqui")
        if not busca:
            _tecla(TECLA_PLAY)
            return "Feito."
        if not no_navegador:
            return {"acao": "youtube_tocar", "busca": busca}  # toca numa aba dentro do Jarvis
        _abrir("https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(busca))
        return f"Tocando {busca} no YouTube."
    if re.search(VERBOS_BUSCA, t):
        busca = busca_de(re.split(VERBOS_BUSCA, t, maxsplit=1)[1], "no google", "na internet")
        if busca:
            _abrir("https://www.google.com/search?q=" + urllib.parse.quote_plus(busca))
            return f"Pesquisando {busca} no Google."
        return "O que o senhor quer que eu pesquise?"

    # ----- abrir sites e programas -----
    abrir = re.search(r"\b(?:abr\w*|abra|inici\w*|execut\w*)\s+(?:o |a |os |as |meu |minha )?(.+)", t)
    if abrir:
        alvo = abrir.group(1)
        for nome, (falado, endereco) in {**SITES, **PROGRAMAS}.items():
            if nome in alvo:
                _abrir(endereco)
                return f"Abrindo {falado}."
        return f"Ainda não conheço {alvo}, senhor. Dá para me ensinar no arquivo de comandos."

    # ----- utilidades -----
    if tem("print", "printa", "captura", "recorte"):
        _abrir("ms-screenclip:")
        return "Pode selecionar a área da tela."
    if tem("status", "sistema", "bateria", "memoria", "processador", "cpu"):
        return _status()

    # ----- conversa -----
    if tem("piada"):
        return random.choice(PIADAS)
    if tem(r"obrigad\w*", "valeu"):
        return random.choice(["Às ordens, senhor.", "Disponha.", "Sempre um prazer, senhor."])
    if tem("quem e voce", "seu nome", "quem e vc"):
        return "Eu sou o Jarvis, seu assistente pessoal. Estou aqui para cuidar do seu notebook."
    if tem("tudo bem", "como voce esta", "como vai"):
        return "Funcionando a cem por cento, senhor. E o senhor?"
    if tem("ajuda", "o que voce sabe", "o que voce faz", "o que voce pode", "comandos"):
        return AJUDA

    # Perguntas de verdade vão para o Claude; o resto (ruído, frase solta) recebe "comando inválido"
    if (re.match(r"(o que|oque|quem|qual|quais|quando|onde|como|quanto|por que|porque|pra que|me explica|explica|me diz|diz|sabe)\b", t)
            or comando.strip().endswith("?")
            or len(t.split()) >= 6):
        return {"acao": "perguntar", "texto": original}
    return "Comando inválido, senhor. Diga ajuda para ver o que eu sei fazer."
