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
# Busca da Microsoft (Bing): combina com o Edge e quase não pede "não sou um robô" para navegador automático,
# ao contrário do Google. Para usar o Google, diga "pesquisa no google X na mini tela".
INICIO = "https://www.bing.com"
BUSCAS = {"bing": "https://www.bing.com/search?q=", "google": "https://www.google.com/search?q=",
          "youtube": "https://www.youtube.com/results?search_query="}

# Erros que mostram que o Playwright desta thread ficou inutilizável (ex.: depois de o antivírus bloquear o
# Edge, ou de o Edge ser fechado por fora). A saída é jogar tudo fora e começar numa thread nova.
ERROS_DE_ESTADO = ("asyncio loop", "Event loop is closed", "Connection closed", "has been closed",
                   "Target closed", "Browser closed")

log = logging.getLogger("jarvis")
_fila = None
_thread = None
_estado = {"contexto": None, "pagina": None, "pw": None, "processo": None}
_trava = threading.Lock()
_trabalhando = threading.Event()   # a thread do Playwright está no meio de algo (abrindo página, clicando...)
_ultimo_quadro = {"jpeg": None, "pedido": False}


# ---------- thread do Playwright ----------
def _laco(fila):
    while True:
        item = fila.get()
        if item is None:  # esta thread foi aposentada
            return
        funcao, args, resposta = item
        _trabalhando.set()
        try:
            resposta.put((True, funcao(*args)))
        except Exception as erro:  # o erro volta para quem chamou
            resposta.put((False, erro))
        finally:
            _trabalhando.clear()


def _novo_trabalhador():
    global _fila, _thread
    _fila = queue.Queue()
    _thread = threading.Thread(target=_laco, args=(_fila,), daemon=True, name="navegador")
    _thread.start()


def _fechar_edges_do_perfil():
    """Fecha os Edges invisíveis que estão usando a pasta da mini tela (sobras de uma tentativa que falhou ou
    de um Jarvis que fechou de mal jeito). Enquanto um deles estiver aberto, nenhum Edge novo consegue usar a
    pasta e a mini tela não abre. O Edge normal do usuário usa outra pasta e não é tocado."""
    import psutil
    alvo = os.path.normcase(os.path.abspath(PERFIL))
    fechados = []
    for processo in psutil.process_iter(["name", "cmdline"]):
        try:
            if (processo.info["name"] or "").lower() != "msedge.exe":
                continue
            linha = os.path.normcase(" ".join(processo.info["cmdline"] or []))
            if alvo in linha:
                processo.kill()
                fechados.append(processo)
        except (psutil.Error, OSError):
            continue
    if fechados:
        # com a memória cheia o Windows leva vários segundos para encerrar de verdade; até lá a pasta fica presa
        _, vivos = psutil.wait_procs(fechados, timeout=15)
        log.info("Mini tela: fechei %d processos do Edge que seguravam a pasta do perfil (%d demoraram)",
                 len(fechados), len(vivos))
        time.sleep(0.5)
    return len(fechados)


def _recomecar():
    """Aposenta a thread do Playwright (com o Edge dela) e cria outra, zerada."""
    with _trava:
        velha, processo = _fila, _estado["processo"]
        _estado.update(contexto=None, pagina=None, pw=None, processo=None, cdp=None, cdp_pagina=None)
        _novo_trabalhador()
    if velha is not None:
        velha.put(None)
    if processo is not None:
        try:
            processo.kill()
        except OSError:
            pass
    _fechar_edges_do_perfil()


def _rodar(funcao, *args, limite=45, recomecar=True):
    """Executa funcao(*args) na thread do Playwright e devolve o resultado (ou levanta o erro).
    Se o Playwright tiver ficado inutilizável, recomeça do zero e tenta mais uma vez."""
    with _trava:
        if _thread is None or not _thread.is_alive():
            _novo_trabalhador()
        fila = _fila
    resposta = queue.Queue(maxsize=1)
    fila.put((funcao, args, resposta))
    try:
        deu_certo, valor = resposta.get(timeout=limite)
    except queue.Empty:
        raise TimeoutError(f"o navegador da mini tela não respondeu em {limite} s") from None
    if deu_certo:
        return valor
    if recomecar and any(trecho in str(valor) for trecho in ERROS_DE_ESTADO):
        log.warning("Mini tela: Playwright inutilizável (%s); recomeçando do zero", str(valor).splitlines()[0])
        _recomecar()
        return _rodar(funcao, *args, limite=limite, recomecar=False)
    raise valor


class Bloqueado(RuntimeError):
    """O Windows (geralmente o antivírus) não deixou o Jarvis abrir o Edge."""


EDGE = os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                    "Microsoft", "Edge", "Application", "msedge.exe")


# --disable-gpu: sem ele, num PC com pouca memória a parte gráfica do Edge invisível cai em páginas pesadas
# (YouTube) e toda foto da página falha com "Unable to capture screenshot"; desenhando pelo processador funciona.
ARGS_EDGE = ["--disable-blink-features=AutomationControlled", "--disable-gpu"]


def _ligar_pelo_playwright(pw):
    return pw.chromium.launch_persistent_context(
        PERFIL, channel="msedge", headless=True, locale="pt-BR",
        viewport={"width": LARGURA, "height": ALTURA}, args=ARGS_EDGE,
    )


def _ligar_pelo_python(pw):
    """Caminho reserva: o próprio Python abre o Edge e o Playwright só se conecta nele.
    Alguns antivírus bloqueiam o Playwright (node) de abrir o Edge, mas deixam o Python."""
    import socket
    import subprocess
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        porta = s.getsockname()[1]
    processo = subprocess.Popen(
        [EDGE, "--headless=new", f"--remote-debugging-port={porta}", f"--user-data-dir={PERFIL}",
         f"--window-size={LARGURA},{ALTURA}", "--lang=pt-BR", *ARGS_EDGE, "--no-first-run", "about:blank"],
        creationflags=subprocess.CREATE_NO_WINDOW)
    _estado["processo"] = processo
    for _ in range(40):  # até 20 s para o Edge abrir a porta
        try:
            navegador = pw.chromium.connect_over_cdp(f"http://127.0.0.1:{porta}", timeout=3000)
            contexto = navegador.contexts[0] if navegador.contexts else navegador.new_context()
            for pagina in contexto.pages:
                pagina.set_viewport_size({"width": LARGURA, "height": ALTURA})
            contexto.on("page", lambda p: p.set_viewport_size({"width": LARGURA, "height": ALTURA}))
            return contexto
        except Exception:
            time.sleep(0.5)
    processo.kill()
    raise RuntimeError("o Edge abriu mas não respondeu")


def _ligar():
    """Liga o Edge: tenta o jeito normal 3 vezes (o bloqueio do antivírus costuma ser passageiro) e depois o reserva."""
    from playwright.sync_api import sync_playwright
    if _estado["pw"] is None:
        _estado["pw"] = sync_playwright().start()
    os.makedirs(PERFIL, exist_ok=True)
    _fechar_edges_do_perfil()  # sobra de uma vez anterior seguraria a pasta
    erros = []
    for tentativa in range(3):
        try:
            return _ligar_pelo_playwright(_estado["pw"])
        except Exception as erro:
            erros.append(str(erro).splitlines()[0])
            log.warning("Mini tela: Edge não abriu (tentativa %d): %s", tentativa + 1, erros[-1])
            _fechar_edges_do_perfil()
            time.sleep(2)
    try:
        contexto = _ligar_pelo_python(_estado["pw"])
        log.info("Mini tela: Edge aberto pelo caminho reserva")
        return contexto
    except Exception as erro:
        erros.append(str(erro).splitlines()[0])
        log.error("Mini tela: Edge não abriu de jeito nenhum: %s", erros)
    if any("EPERM" in e or "Acesso negado" in e or "WinError 5" in e for e in erros):
        raise Bloqueado("O Windows bloqueou o navegador da mini tela, provavelmente o antivírus. Tente de novo em "
                        "alguns segundos; se continuar, libere a pasta do Jarvis no antivírus.")
    raise Bloqueado("Não consegui ligar o navegador da mini tela agora. Tente de novo em alguns segundos.")


def _pagina():
    """Liga o Edge na primeira vez. Sempre devolve a aba ativa (a mais nova, se o site abriu outra)."""
    if _estado["contexto"] is None:
        contexto = _ligar()
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
            if _estado["processo"] is not None:  # Edge aberto pelo caminho reserva
                _estado["processo"].kill()
            _estado.update(contexto=None, pagina=None, pw=None, processo=None, cdp=None, cdp_pagina=None)


# ---------- endereços ----------
def endereco(texto, buscador="bing"):
    """"g1.com.br" -> https://g1.com.br; "receita de bolo" -> busca no Bing; link completo fica igual."""
    texto = texto.strip()
    if re.match(r"(?:https?|file)://", texto):
        return texto
    if re.fullmatch(r"[\w.-]+\.[a-z]{2,}(?:/\S*)?", texto, re.I) and " " not in texto:
        return "https://" + texto
    return BUSCAS.get(buscador, BUSCAS["bing"]) + urllib.parse.quote_plus(texto)


# ---------- ações (as mesmas do modo tela, para o agente_tela usar) ----------
def ligado():
    return _estado["contexto"] is not None


def preparar():
    _rodar(_pagina, limite=120)


def abrir(texto=INICIO, buscador="bing"):
    def _abrir(url):
        pagina = _pagina()
        try:
            # "commit": volta assim que a página começa a chegar, para a mini tela já ir mostrando o carregamento
            pagina.goto(url, wait_until="commit", timeout=45000)
            pagina.wait_for_load_state("domcontentloaded", timeout=10000)
        except Exception as erro:  # página lenta (ou PC sem memória): mostra o que já carregou
            log.warning("Navegador: %s demorou para abrir (%s)", url, str(erro).splitlines()[0])
        return pagina.url
    # ligar o Edge pode levar várias tentativas, e o PC pode estar lento: espera bastante
    return _rodar(_abrir, endereco(texto or INICIO, buscador), limite=180)


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


_ultimo_estado = {"url": "", "titulo": ""}


def estado():
    """Endereço e título da página. Se o Edge estiver ocupado (página pesada carregando), devolve o último
    conhecido em vez de travar quem perguntou."""
    if not ligado():
        return {"url": "", "titulo": ""}

    def _ler():
        pagina = _pagina()
        try:
            titulo = pagina.title()
        except Exception:
            titulo = ""
        return {"url": pagina.url, "titulo": titulo}
    try:
        _ultimo_estado.update(_rodar(_ler, limite=20))
    except Exception:
        log.info("Mini tela: Edge ocupado; usando o último endereço conhecido")
    return dict(_ultimo_estado)


def _foto(pagina, formato="jpeg", qualidade=60):
    """Foto da parte visível da página. Usa o protocolo do próprio Edge (Page.captureScreenshot), que não espera
    fontes nem animações: o screenshot comum do Playwright travava em páginas pesadas, como o YouTube."""
    import base64
    try:
        if _estado.get("cdp_pagina") is not pagina:
            _estado["cdp"] = pagina.context.new_cdp_session(pagina)
            _estado["cdp_pagina"] = pagina
        parametros = {"format": formato, "captureBeyondViewport": False}
        if formato == "jpeg":
            parametros["quality"] = qualidade
        return base64.b64decode(_estado["cdp"].send("Page.captureScreenshot", parametros)["data"])
    except Exception:
        _estado["cdp_pagina"] = None
        log.info("Mini tela: foto pelo protocolo falhou; usando a do Playwright", exc_info=True)
        if formato == "jpeg":
            return pagina.screenshot(type="jpeg", quality=qualidade, timeout=20000, animations="disabled")
        return pagina.screenshot(type="png", timeout=20000, animations="disabled")


def quadro(qualidade=60):
    """Imagem atual da mini tela em JPEG (bytes), para a interface. None se o navegador está desligado."""
    return quadro_ao_vivo(qualidade)[0]


def quadro_ao_vivo(qualidade=60):
    """Devolve (jpeg, carregando). Se o navegador estiver ocupado (abrindo uma página pesada, por exemplo),
    devolve a última imagem em vez de esperar: assim a mini tela nunca fica em branco nem pisca, e os pedidos
    de imagem não se acumulam na fila atrasando os cliques."""
    if not ligado():
        return None, False
    if _trabalhando.is_set() or _ultimo_quadro["pedido"]:
        return _ultimo_quadro["jpeg"], True
    _ultimo_quadro["pedido"] = True
    try:
        jpeg = _rodar(lambda: _foto(_pagina(), "jpeg", qualidade), limite=8, recomecar=False)
        _ultimo_quadro["jpeg"] = jpeg
        return jpeg, False
    except Exception:
        return _ultimo_quadro["jpeg"], True
    finally:
        _ultimo_quadro["pedido"] = False


# Botões, links e campos visíveis, com o centro de cada um: o agente clica pelo número em vez de adivinhar
# a posição na foto (muito mais certeiro em páginas cheias, como YouTube e Google Maps).
_JS_ELEMENTOS = r"""() => {
  const seletor = 'a[href],button,input:not([type=hidden]),textarea,select,[role=button],[role=link],[role=tab],'
    + '[role=menuitem],[role=option],[role=searchbox],[role=textbox],[onclick],[contenteditable=true]';
  const saida = [], vistos = new Set();
  for (const el of document.querySelectorAll(seletor)) {
    const r = el.getBoundingClientRect();
    if (r.width < 6 || r.height < 6 || r.bottom < 0 || r.right < 0 || r.top > innerHeight || r.left > innerWidth) continue;
    const st = getComputedStyle(el);
    if (st.visibility === 'hidden' || st.display === 'none' || Number(st.opacity) < 0.1) continue;
    const x = Math.round(Math.min(Math.max(r.left + r.width / 2, 1), innerWidth - 1));
    const y = Math.round(Math.min(Math.max(r.top + r.height / 2, 1), innerHeight - 1));
    const topo = document.elementFromPoint(x, y);
    if (topo && topo !== el && !el.contains(topo) && !topo.contains(el)) continue;  // coberto por outra coisa
    const chave = x + ',' + y;
    if (vistos.has(chave)) continue;
    vistos.add(chave);
    const texto = (el.getAttribute('aria-label') || el.innerText || el.value || el.getAttribute('title')
      || el.getAttribute('placeholder') || el.getAttribute('alt') || '').trim().replace(/\s+/g, ' ').slice(0, 70);
    const tag = el.tagName.toLowerCase();
    const tipo = tag === 'input' ? 'campo' : tag === 'textarea' || el.isContentEditable || /box/.test(el.getAttribute('role') || '') ? 'campo'
      : tag === 'a' || el.getAttribute('role') === 'link' ? 'link' : tag === 'select' ? 'lista' : 'botao';
    if (!texto && tipo !== 'campo') continue;
    saida.push({x, y, tipo, texto});
    if (saida.length >= 90) break;
  }
  return saida;
}"""


def elementos():
    """[{id, x, y, tipo, texto}] do que dá para clicar ou preencher na parte visível da página."""
    lista = _rodar(lambda: _pagina().evaluate(_JS_ELEMENTOS), limite=25)
    return [{"id": n, **item} for n, item in enumerate(lista, 1)]


def capturar():
    """Para o agente: salva a imagem da página e devolve (caminho, largura, altura)."""
    os.makedirs(os.path.dirname(CAPTURA), exist_ok=True)
    try:
        imagem = _rodar(lambda: _foto(_pagina(), "png"), limite=40)
    except TimeoutError:
        imagem = _ultimo_quadro["jpeg"]  # Edge muito ocupado: o agente olha a última imagem da mini tela
        if not imagem:
            raise
    with open(CAPTURA, "wb") as arquivo:
        arquivo.write(imagem)
    return CAPTURA, LARGURA, ALTURA


def desligar():
    """Fecha o Edge sem esperar: fechar às vezes demora dezenas de segundos e não pode travar o Jarvis.
    (Ao fechar o Jarvis, o Playwright fecha o Edge sozinho.)"""
    if ligado():
        _fila.put((_desligar, (), queue.Queue(maxsize=1)))
