"""Navegador do Jarvis: um Microsoft Edge invisível, controlado pelo Playwright, que aparece ao vivo numa
"mini tela" dentro da interface.

Por que não um <iframe>: Google, Instagram, GitHub e muitos outros sites se recusam a abrir dentro de outra
página, e o Jarvis não consegue clicar nem ler o que está num iframe de outro site. Aqui o site roda num
navegador de verdade; a interface mostra a imagem dele (servidor.py entrega o quadro) e manda de volta os
cliques, a rolagem e as teclas. O Jarvis usa as mesmas funções (capturar, clicar, digitar, tecla, rolar) que o
modo tela, então o agente_tela.py também consegue agir sozinho dentro da mini tela.

O perfil fica em navegador_perfil/: logins feitos na mini tela continuam valendo na próxima vez.
O Playwright só aceita ser usado de uma thread; por isso tudo passa por uma fila numa thread própria.
"""
import logging
import os
import queue
import re
import threading
import time
import urllib.parse

PASTA = os.path.dirname(os.path.abspath(__file__))
PERFIL = os.path.join(PASTA, "navegador_perfil")
CAPTURA = os.path.join(os.environ.get("TEMP", PASTA), "jarvis_navegador", "jarvis_tela.png")
LARGURA, ALTURA = 1280, 800
INICIO = "https://www.google.com"

log = logging.getLogger("jarvis")
_fila = queue.Queue()
_thread = None
_estado = {"contexto": None, "pagina": None, "pw": None}
_trava = threading.Lock()


# ---------- thread do Playwright ----------
def _laco():
    while True:
        funcao, args, resposta = _fila.get()
        try:
            resposta.put((True, funcao(*args)))
        except Exception as erro:  # o erro volta para quem chamou
            resposta.put((False, erro))


def _rodar(funcao, *args, limite=45):
    """Executa funcao(*args) na thread do Playwright e devolve o resultado (ou levanta o erro)."""
    global _thread
    with _trava:
        if _thread is None or not _thread.is_alive():
            _thread = threading.Thread(target=_laco, daemon=True, name="navegador")
            _thread.start()
    resposta = queue.Queue(maxsize=1)
    _fila.put((funcao, args, resposta))
    deu_certo, valor = resposta.get(timeout=limite)
    if not deu_certo:
        raise valor
    return valor


def _pagina():
    """Liga o Edge na primeira vez. Sempre devolve a aba ativa (a mais nova, se o site abriu outra)."""
    if _estado["contexto"] is None:
        from playwright.sync_api import sync_playwright
        _estado["pw"] = sync_playwright().start()
        os.makedirs(PERFIL, exist_ok=True)
        contexto = _estado["pw"].chromium.launch_persistent_context(
            PERFIL, channel="msedge", headless=True, locale="pt-BR",
            viewport={"width": LARGURA, "height": ALTURA},
            args=["--disable-blink-features=AutomationControlled"],
        )
        contexto.on("page", lambda pagina: _estado.update(pagina=pagina))  # site abriu nova aba: segue nela
        _estado["contexto"] = contexto
        _estado["pagina"] = contexto.pages[0] if contexto.pages else contexto.new_page()
        log.info("Navegador do Jarvis ligado (Edge, perfil em %s)", PERFIL)
    pagina = _estado["pagina"]
    if pagina.is_closed():
        abertas = [p for p in _estado["contexto"].pages if not p.is_closed()]
        pagina = _estado["pagina"] = abertas[-1] if abertas else _estado["contexto"].new_page()
    return pagina


def _desligar():
    if _estado["contexto"] is not None:
        try:
            for pagina in _estado["contexto"].pages:
                pagina.close(run_before_unload=False)  # sem isso o Edge às vezes fica esperando e não fecha
            _estado["contexto"].close()
            _estado["pw"].stop()
        finally:
            _estado.update(contexto=None, pagina=None, pw=None)


# ---------- endereços ----------
def endereco(texto):
    """"g1.com.br" -> https://g1.com.br; "receita de bolo" -> busca no Google; link completo fica igual."""
    texto = texto.strip()
    if re.match(r"https?://", texto):
        return texto
    if re.fullmatch(r"[\w.-]+\.[a-z]{2,}(?:/\S*)?", texto, re.I) and " " not in texto:
        return "https://" + texto
    return "https://www.google.com/search?q=" + urllib.parse.quote_plus(texto)


# ---------- ações (as mesmas do modo tela, para o agente_tela usar) ----------
def ligado():
    return _estado["contexto"] is not None


def preparar():
    _rodar(_pagina)


def abrir(texto=INICIO):
    def _abrir(url):
        pagina = _pagina()
        try:
            pagina.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception as erro:  # página lenta: mostra o que já carregou
            log.warning("Navegador: %s demorou para abrir (%s)", url, erro)
        return pagina.url
    return _rodar(_abrir, endereco(texto or INICIO))


def clicar(x, y, duplo=False, botao="left"):
    _rodar(lambda: _pagina().mouse.click(x, y, button=botao, click_count=2 if duplo else 1))
    time.sleep(0.4)


def digitar(texto):
    _rodar(lambda: _pagina().keyboard.type(texto[:500], delay=15))


_TECLAS = {"enter": "Enter", "tab": "Tab", "esc": "Escape", "escape": "Escape", "backspace": "Backspace",
           "delete": "Delete", "del": "Delete", "space": " ", "espaco": " ", "up": "ArrowUp", "down": "ArrowDown",
           "left": "ArrowLeft", "right": "ArrowRight", "pageup": "PageUp", "pagedown": "PageDown", "home": "Home",
           "end": "End", "ctrl": "Control", "control": "Control", "shift": "Shift", "alt": "Alt"}


def tecla(nome):
    """'enter', 'ctrl+a', ou o nome de tecla do navegador ('ArrowDown', 'Backspace')."""
    partes = [p for p in nome.replace(" ", "").split("+") if p]
    combinacao = "+".join(_TECLAS.get(p.lower(), p if len(p) > 1 else p.lower()) for p in partes)
    if combinacao:
        _rodar(lambda: _pagina().keyboard.press(combinacao))


def rolar(cliques):
    """Igual ao modo tela: cliques negativos descem, positivos sobem."""
    rolar_pixels(-int(cliques) * 120)


def rolar_pixels(dy):
    _rodar(lambda: _pagina().mouse.wheel(0, dy))


def voltar():
    _rodar(lambda: _pagina().go_back(wait_until="domcontentloaded", timeout=15000))


def avancar():
    _rodar(lambda: _pagina().go_forward(wait_until="domcontentloaded", timeout=15000))


def recarregar():
    _rodar(lambda: _pagina().reload(wait_until="domcontentloaded", timeout=30000))


def estado():
    if not ligado():
        return {"url": "", "titulo": ""}
    def _ler():
        pagina = _pagina()
        try:
            titulo = pagina.title()
        except Exception:
            titulo = ""
        return {"url": pagina.url, "titulo": titulo}
    return _rodar(_ler, limite=10)


def quadro(qualidade=60):
    """Imagem atual da mini tela em JPEG (bytes), para a interface. None se o navegador está desligado."""
    if not ligado():
        return None
    return _rodar(lambda: _pagina().screenshot(type="jpeg", quality=qualidade, timeout=5000), limite=10)


def capturar():
    """Para o agente: salva a imagem da página e devolve (caminho, largura, altura)."""
    os.makedirs(os.path.dirname(CAPTURA), exist_ok=True)
    _rodar(lambda: _pagina().screenshot(path=CAPTURA, timeout=10000))
    return CAPTURA, LARGURA, ALTURA


def desligar():
    """Fecha o Edge sem esperar: fechar às vezes demora dezenas de segundos e não pode travar o Jarvis.
    (Ao fechar o Jarvis, o Playwright fecha o Edge sozinho.)"""
    if ligado():
        _fila.put((_desligar, (), queue.Queue(maxsize=1)))
