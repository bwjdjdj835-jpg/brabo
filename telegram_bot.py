"""Bot do Telegram: comandar o Jarvis pelo celular, de qualquer lugar.

Usa só a biblioteca padrão (urllib), por long polling. NÃO abre nenhuma porta do notebook:
é o Jarvis que pergunta à API do Telegram se chegou mensagem. Só IDs autorizados podem usar.
O token fica no .env, nunca falado nem na biblioteca.
"""
import json
import logging
import os
import threading
import time
import urllib.parse
import urllib.request

import segredos

PASTA = os.path.dirname(os.path.abspath(__file__))
IDS = os.path.join(PASTA, "telegram_ids.json")
API = "https://api.telegram.org/bot{token}/{metodo}"

AJUDA = (
    "Comandos do Jarvis:\n"
    "/status — como está o notebook\n"
    "/ajuda — esta mensagem\n\n"
    "Ou mande o que quiser, igual à voz:\n"
    "• que horas são\n"
    "• cria um site de barbearia\n"
    "• onde está o APK\n"
    "• manda um email para fulano@x.com dizendo ...\n\n"
    "Ações de risco (e-mail, apagar, criar app) pedem confirmação: responda sim para confirmar."
)

log = logging.getLogger("jarvis")


class TelegramBot:
    def __init__(self, token, autorizados, responder, status):
        self._token = token
        self._autorizados = autorizados          # {id(str): nome}
        self._responder = responder              # funcao(texto) -> resposta em texto
        self._status = status                    # funcao() -> dict do sistema
        self._parar = threading.Event()
        self._ultimo = 0

    # ---------- chamadas à API ----------
    def _chamar(self, metodo, **dados):
        url = API.format(token=self._token, metodo=metodo)
        corpo = urllib.parse.urlencode(dados).encode("utf-8")
        try:
            with urllib.request.urlopen(url, data=corpo, timeout=65) as resposta:
                return json.loads(resposta.read().decode("utf-8"))
        except Exception:
            return None

    def enviar(self, chat_id, texto):
        self._chamar("sendMessage", chat_id=chat_id, text=texto[:4000])

    def avisar_todos(self, texto):
        """Manda um aviso para todos os autorizados (ex.: tarefa concluída)."""
        for id_chat in self._autorizados:
            self.enviar(id_chat, texto)

    # ---------- laço principal ----------
    def rodar(self):
        me = self._chamar("getMe")
        nome = me["result"]["username"] if me and me.get("ok") else "?"
        log.info("Bot do Telegram iniciado: @%s", nome)
        while not self._parar.is_set():
            atualizacoes = self._chamar("getUpdates", offset=self._ultimo + 1, timeout=50)
            if not atualizacoes or not atualizacoes.get("ok"):
                time.sleep(3)
                continue
            for item in atualizacoes["result"]:
                self._ultimo = item["update_id"]
                self._tratar(item.get("message") or {})

    def parar(self):
        self._parar.set()

    def _tratar(self, mensagem):
        texto = (mensagem.get("text") or "").strip()
        chat = mensagem.get("chat", {})
        id_chat = str(chat.get("id", ""))
        if not texto or not id_chat:
            return

        if id_chat not in self._autorizados:
            nome = (chat.get("first_name") or "") + " (@" + (chat.get("username") or "?") + ")"
            log.warning("Telegram negado para %s id %s: %r", nome.strip(), id_chat, texto[:80])
            self.enviar(id_chat, "Você não tem autorização para usar este bot.")
            return

        log.info("Telegram de %s: %s", self._autorizados[id_chat], texto)
        try:
            resposta = self._comando(texto)
        except Exception:
            log.exception("Erro ao tratar comando do Telegram")
            resposta = "Desculpe, senhor. Algo deu errado."
        self.enviar(id_chat, resposta or "Feito, senhor.")

    def _comando(self, texto):
        baixo = texto.lower()
        if baixo in ("/start", "/ajuda", "/help", "/menu"):
            return "Olá, senhor. Sou o Jarvis.\n\n" + AJUDA
        if baixo == "/status":
            s = self._status()
            d = s.get("detalhes", {})
            return (f"Sistema do notebook:\n"
                    f"Processador: {s.get('cpu')}%\n"
                    f"Memória: {s.get('ram')}% ({d.get('ram_usada')} de {d.get('ram_total')} GB)\n"
                    f"Disco: {s.get('disco')}% ({d.get('disco_livre')} GB livres)\n"
                    f"Bateria: {s.get('bateria')}%{' carregando' if s.get('carregando') else ''}\n"
                    f"Processos: {d.get('processos')} · ligado há {d.get('uptime_h')} h")
        return self._responder(texto)


def preparar_ids():
    if not os.path.exists(IDS):
        with open(IDS, "w", encoding="utf-8") as arquivo:
            json.dump({"_ajuda": "id do Telegram -> nome. Descubra seu id com @userinfobot.",
                       "123456789": "Dono"}, arquivo, ensure_ascii=False, indent=2)


def _autorizados():
    """IDs autorizados: o telegram_ids.json e também o JARVIS_TELEGRAM_IDS do .env."""
    ids = {}
    try:
        with open(IDS, encoding="utf-8") as arquivo:
            for chave, nome in json.load(arquivo).items():
                if chave.isdigit():
                    ids[chave] = nome
    except (OSError, json.JSONDecodeError):
        pass
    for parte in (segredos.obter("JARVIS_TELEGRAM_IDS", "") or "").split(","):
        parte = parte.strip()
        if parte.isdigit():
            ids.setdefault(parte, "Dono")
    return ids


def iniciar(responder, status):
    """Cria e inicia o bot numa thread, se houver token no .env. Devolve o bot ou None."""
    preparar_ids()
    token = segredos.obter("JARVIS_TELEGRAM_TOKEN")
    if not token:
        log.info("Bot do Telegram desligado (sem token no .env)")
        return None
    autorizados = _autorizados()
    if not autorizados:
        log.warning("Telegram tem token mas nenhum ID autorizado; ninguém poderá usar")
    bot = TelegramBot(token, autorizados, responder, status)
    threading.Thread(target=bot.rodar, daemon=True).start()
    return bot
