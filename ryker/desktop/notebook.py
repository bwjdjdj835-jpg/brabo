"""Mini notebook: a tela real do notebook ao vivo dentro do Braga, e o controle de verdade (mouse e teclado).

- CapturaTela:  fotos da tela principal com o mss (até ~20 por segundo), com o mouse desenhado, em JPEG.
- ControleReal: converte um ponto da mini tela (0 a 1) para pixels reais e age com o pyautogui: clique
                (esquerdo, direito, duplo), mover, digitar, teclas especiais e rolar.
- Sessao:       pausar/retomar/parar, correções do senhor no meio da tarefa e o registro das ações.
- AlvoNotebook: o que o agente_tela precisa (capturar, clicar, digitar...) para o Braga agir sozinho aqui.

Primeira pessoa: enquanto alguém olha o notebook, a janela do Braga fica por cima de tudo e fora da captura
(SetWindowDisplayAffinity, só nas janelas do próprio Braga). Os programas de verdade ficam ATRÁS do Braga e a
mini tela mostra esses programas: tudo acontece dentro do Braga, sem um Braga dentro do outro e sem janela
pulando na frente. Os cliques atravessam a janela do Braga só durante o clique (WS_EX_TRANSPARENT) e chegam ao
programa de trás. Ao fechar o notebook, tudo volta ao normal.

Freio de segurança (pyautogui.FAILSAFE): ligado por padrão; jogar o mouse no canto superior esquerdo para tudo.
Dá para desligar no botão "freio" do notebook.
"""
import collections
import ctypes
import datetime
import io
import logging
import queue
import threading
import time
from ctypes import wintypes

from PIL import Image, ImageDraw

import identidade
import tela

TITULO_FLUTUANTE = "Braga · notebook"

log = logging.getLogger("jarvis")
user32 = ctypes.windll.user32
user32.WindowFromPoint.argtypes = [wintypes.POINT]
user32.WindowFromPoint.restype = wintypes.HWND
user32.GetAncestor.restype = wintypes.HWND
user32.FindWindowW.restype = wintypes.HWND
user32.GetForegroundWindow.restype = wintypes.HWND
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                wintypes.UINT]
user32.SetLayeredWindowAttributes.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_ubyte, wintypes.DWORD]

GWL_EXSTYLE, WS_EX_LAYERED, WS_EX_TRANSPARENT, LWA_ALPHA = -20, 0x80000, 0x20, 0x2
HWND_TOPMOST, HWND_NOTOPMOST = wintypes.HWND(-1), wintypes.HWND(-2)
SWP_SEM_MEXER = 0x0001 | 0x0002 | 0x0010  # SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE


def _mss():
    import mss
    return getattr(mss, "MSS", mss.mss)()


def janelas_do_braga():
    """{nome: hwnd} das janelas abertas do Braga (principal e notebook flutuante)."""
    achadas = {}
    for nome, titulo in (("principal", identidade.SIGLA), ("flutuante", TITULO_FLUTUANTE)):
        hwnd = user32.FindWindowW(None, titulo)
        if hwnd:
            achadas[nome] = hwnd
    return achadas


def _retangulo(hwnd):
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


WDA_NENHUM, WDA_FORA_DA_CAPTURA = 0x0, 0x11


def fora_da_captura(sim=True):
    """Enquanto o mini notebook está aberto, as janelas do Braga não entram nas fotos da tela (o mesmo recurso que
    os programas de reunião usam). Sem isso o notebook filma a si mesmo, um Braga dentro do outro, sem fim.
    Devolve as janelas em que o Windows recusou: essas são cobertas na imagem."""
    recusadas = []
    for hwnd in janelas_do_braga().values():
        if not user32.SetWindowDisplayAffinity(hwnd, WDA_FORA_DA_CAPTURA if sim else WDA_NENHUM) and sim:
            recusadas.append(hwnd)
    return recusadas


def _principal_visivel():
    hwnd = janelas_do_braga().get("principal")
    return hwnd if hwnd and user32.IsWindowVisible(hwnd) and not user32.IsIconic(hwnd) else None


def primeira_pessoa(sim=True):
    """O notebook "dentro" do Braga: a janela principal fica por cima de tudo (sem roubar o foco) e todas as do
    Braga saem da captura. Os programas abrem e funcionam atrás dele. Devolve as janelas a cobrir na imagem."""
    recusadas = fora_da_captura(sim)
    hwnd = janelas_do_braga().get("principal")
    if hwnd:
        user32.SetWindowPos(hwnd, HWND_TOPMOST if sim else HWND_NOTOPMOST, 0, 0, 0, 0, SWP_SEM_MEXER)
    return recusadas


class _Atravessar:
    """Durante um clique ou rolagem, a janela do Braga vira "vidro": o mouse passa por ela e chega ao programa de
    trás. Depois volta ao normal e continua por cima. Guarda a janela que ficou com o foco (para digitar nela)."""

    def __init__(self, controle, x, y):
        self.controle, self.x, self.y, self.hwnd, self.estilo = controle, x, y, None, 0

    def __enter__(self):
        hwnd = _principal_visivel()
        if hwnd:
            esquerda, topo, direita, baixo = _retangulo(hwnd)
            if esquerda <= self.x < direita and topo <= self.y < baixo:
                self.hwnd, self.estilo = hwnd, user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, self.estilo | WS_EX_LAYERED | WS_EX_TRANSPARENT)
                user32.SetLayeredWindowAttributes(hwnd, 0, 255, LWA_ALPHA)  # continua 100% visível
        return self

    def __exit__(self, *erro):
        time.sleep(0.12)
        frente = user32.GetForegroundWindow()
        if frente and frente not in janelas_do_braga().values():
            self.controle.alvo_hwnd = frente  # o programa que recebeu o clique
        if self.hwnd:
            user32.SetWindowLongW(self.hwnd, GWL_EXSTYLE, self.estilo)
            user32.SetWindowPos(self.hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_SEM_MEXER)
        return False


def _cobrir(imagem, monitor, janelas):
    """Plano B: pinta por cima das janelas do Braga que o Windows não deixou tirar da captura."""
    if not janelas:
        return
    escala = imagem.width / monitor["width"]
    desenho = ImageDraw.Draw(imagem)
    for hwnd in janelas:
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            continue
        esquerda, topo, direita, baixo = ((v - o) * escala for v, o in zip(
            _retangulo(hwnd), (monitor["left"], monitor["top"], monitor["left"], monitor["top"])))
        desenho.rectangle((esquerda, topo, direita, baixo), fill=(5, 11, 22), outline=(61, 139, 255), width=2)
        desenho.text(((esquerda + direita) / 2 - 40, (topo + baixo) / 2), "janela do Braga", fill=(96, 165, 250))


# ---------- captura ----------
class CapturaTela:
    LARGURA = 1280        # largura do quadro mandado para a interface
    OCIOSO = 3.0          # sem ninguém olhando por 3 s, a captura contínua para (poupa o processador)
    FPS = 10              # fotos por segundo da captura contínua

    def __init__(self):
        self._trava = threading.Lock()
        self._jpg = None
        self._bruta = None       # última foto crua da linha de captura
        self._numero_bruta = 0
        self._numero_jpg = -1
        self._pedido = 0.0
        self._linha = None
        self._cobrir = []    # janelas do Braga que o Windows não tirou da captura
        self.numero = 0
        self.monitor = None  # {"left", "top", "width", "height"} da tela principal

    def tamanho(self):
        if not self.monitor:
            with _mss() as sct:
                self.monitor = dict(sct.monitors[1])
        return self.monitor

    def foto(self, largura=None, com_mouse=True):
        """Foto da tela principal como imagem PIL, reduzida para `largura` (se passar dela)."""
        with _mss() as sct:
            self.monitor = dict(sct.monitors[1])
            bruta = sct.grab(self.monitor)
        imagem = Image.frombytes("RGB", bruta.size, bruta.bgra, "raw", "BGRX")
        if largura and imagem.width > largura:
            imagem = imagem.resize((largura, round(imagem.height * largura / imagem.width)), Image.BILINEAR)
        _cobrir(imagem, self.monitor, self._cobrir)
        if com_mouse:
            ponto = wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(ponto))
            escala = imagem.width / self.monitor["width"]
            x = (ponto.x - self.monitor["left"]) * escala
            y = (ponto.y - self.monitor["top"]) * escala
            desenho = ImageDraw.Draw(imagem)
            desenho.ellipse((x - 8, y - 8, x + 8, y + 8), outline=(56, 225, 255), width=3)
            desenho.ellipse((x - 2, y - 2, x + 2, y + 2), fill=(255, 255, 255))
        return imagem

    def _capturar_sem_parar(self):
        """Linha própria só para fotografar (a parte lenta, ~70 ms neste PC); a conversão fica com quem pede."""
        ajuste = 0.0
        try:
            with _mss() as sct:
                while time.time() - self._pedido < self.OCIOSO:
                    inicio = time.time()
                    if inicio - ajuste > 1:  # janelas novas do Braga (o flutuante) também saem da captura
                        self._cobrir, ajuste = primeira_pessoa(True), inicio
                    self.monitor = dict(sct.monitors[1])
                    self._bruta = sct.grab(self.monitor)
                    self._numero_bruta += 1
                    # no máximo FPS fotos por segundo: cada foto também usa a placa de vídeo, que o quarto 3D divide
                    time.sleep(max(0.0, 1 / self.FPS - (time.time() - inicio)))
        finally:
            primeira_pessoa(False)  # notebook fechado: o Braga volta a ser janela normal e a aparecer nos prints
            self._cobrir = []
            self._linha = None

    def quadro(self):
        """JPEG mais recente, para a mini tela (~13 por segundo neste PC). None enquanto liga."""
        self._pedido = time.time()
        with self._trava:
            if self._linha is None:
                self._linha = threading.Thread(target=self._capturar_sem_parar, daemon=True)
                self._linha.start()
            limite = time.time() + 1.5
            while self._bruta is None and time.time() < limite:  # primeira foto ainda saindo
                time.sleep(0.05)
            bruta = self._bruta
            if bruta is None or self._numero_bruta == self._numero_jpg:
                return self._jpg
            self._numero_jpg = self._numero_bruta
            imagem = Image.frombuffer("RGBX", bruta.size, bruta.bgra, "raw", "BGRX", 0, 1)
            imagem = imagem.resize((self.LARGURA, round(bruta.size[1] * self.LARGURA / bruta.size[0])),
                                   Image.NEAREST).convert("RGB")
            _cobrir(imagem, self.monitor, self._cobrir)
            ponto = wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(ponto))
            escala = imagem.width / self.monitor["width"]
            x, y = (ponto.x - self.monitor["left"]) * escala, (ponto.y - self.monitor["top"]) * escala
            desenho = ImageDraw.Draw(imagem)
            desenho.ellipse((x - 8, y - 8, x + 8, y + 8), outline=(56, 225, 255), width=3)
            desenho.ellipse((x - 2, y - 2, x + 2, y + 2), fill=(255, 255, 255))
            saida = io.BytesIO()
            imagem.save(saida, "JPEG", quality=60)
            self._jpg = saida.getvalue()
            self.numero += 1
            return self._jpg


# ---------- controle real ----------
class ControleReal:
    TECLAS = {"win": "winleft", "windows": "winleft", "esc": "escape", "apagar": "backspace", "del": "delete",
              "pgup": "pageup", "pgdn": "pagedown", "control": "ctrl", "meta": "winleft"}

    def __init__(self, captura):
        self.captura = captura
        self.ultimo_ponto = None  # onde foi o último clique
        self.alvo_hwnd = None     # programa que recebeu o último clique (o teclado vai para ele)

    def preparar(self):
        tela.preparar()  # DPI: pixels da foto = pixels do clique

    @property
    def freio(self):
        import pyautogui
        return pyautogui.FAILSAFE

    @freio.setter
    def freio(self, ligado):
        import pyautogui
        pyautogui.FAILSAFE = bool(ligado)

    def real(self, fx, fy):
        """Ponto da mini tela (0 a 1) -> pixel real da tela principal."""
        m = self.captura.tamanho()
        fx, fy = min(max(float(fx), 0.0), 1.0), min(max(float(fy), 0.0), 1.0)
        return round(m["left"] + fx * (m["width"] - 1)), round(m["top"] + fy * (m["height"] - 1))

    def clicar(self, fx, fy, botao="left", duplo=False):
        import pyautogui
        self.preparar()
        x, y = self.real(fx, fy)
        with _Atravessar(self, x, y):  # o clique passa pelo Braga e chega ao programa de trás
            pyautogui.moveTo(x, y, duration=0.15)
            if duplo:
                pyautogui.doubleClick(x, y)
            else:
                pyautogui.click(x, y, button=botao)
        self.ultimo_ponto = (x, y)

    def mover(self, fx, fy):
        import pyautogui
        self.preparar()
        pyautogui.moveTo(*self.real(fx, fy), duration=0.15)

    def deslizar(self, dx, dy):
        """Touchpad: o dedo deslizando move o cursor de verdade (dx, dy em pixels reais)."""
        import pyautogui
        self.preparar()
        pyautogui.moveRel(int(dx), int(dy), duration=0)
        self.ultimo_ponto = tuple(pyautogui.position())

    def tocar(self, botao="left", duplo=False):
        """Touchpad: toque (ou botão do touchpad) clica onde o cursor está, atravessando o Braga."""
        import pyautogui
        self.preparar()
        x, y = pyautogui.position()
        with _Atravessar(self, x, y):
            if duplo:
                pyautogui.doubleClick(x, y)
            else:
                pyautogui.click(x, y, button=botao)
        self.ultimo_ponto = (x, y)

    def rolar(self, cliques):
        import pyautogui
        self.preparar()
        x, y = self.ultimo_ponto or pyautogui.position()
        with _Atravessar(self, x, y):  # a rodinha também vai para o programa de trás, não para o Braga
            pyautogui.moveTo(x, y)
            pyautogui.scroll(int(cliques))

    def focar_alvo(self):
        """Antes de digitar pelo painel do Braga: o teclado volta para o programa do último clique (ele continua
        atrás do Braga na tela, mas é quem recebe as teclas)."""
        if self.alvo_hwnd and user32.IsWindow(self.alvo_hwnd):
            user32.SetForegroundWindow(self.alvo_hwnd)
            time.sleep(0.2)

    def digitar(self, texto):
        """Escreve o texto. Com acentos, cola pela área de transferência (o pyautogui só digita sem acento)."""
        import pyautogui
        texto = str(texto)[:2000]
        if texto.isascii():
            pyautogui.write(texto, interval=0.02)
        else:
            _copiar(texto)
            pyautogui.hotkey("ctrl", "v")
        time.sleep(0.15)

    def tecla(self, nome):
        """'enter', 'tab', 'win', 'esc', 'ctrl+c', 'alt+tab'..."""
        import pyautogui
        self.preparar()
        partes = [self.TECLAS.get(p.strip().lower(), p.strip().lower())
                  for p in str(nome).replace(" ", "").split("+") if p.strip()]
        if len(partes) > 1:
            pyautogui.hotkey(*partes)
        elif partes:
            pyautogui.press(partes[0])
        time.sleep(0.15)


def _copiar(texto):
    """Põe o texto na área de transferência do Windows."""
    import subprocess
    subprocess.run(["clip"], input=texto.encode("utf-16-le"), creationflags=subprocess.CREATE_NO_WINDOW,
                   check=False, timeout=10)


# ---------- sessão: pausa, parada, correções e registro ----------
class Sessao:
    def __init__(self):
        self.pausado = threading.Event()
        self.parar = threading.Event()
        self.correcoes = queue.Queue()
        self.acoes = collections.deque(maxlen=80)
        self.controlando = False
        self.tarefa = ""
        self.confirmacao = None  # {"fx", "fy", "fala"}: botão de enviar/publicar/excluir esperando o "sim"

    def comecar(self, tarefa):
        self.parar.clear()
        self.pausado.clear()
        self.correcoes_novas()
        self.controlando, self.tarefa = True, tarefa
        self.registrar(f"Tarefa: {tarefa}")

    def terminar(self, resumo=""):
        self.controlando = False
        self.pausado.clear()
        if resumo:
            self.registrar(f"Fim: {resumo}")

    def registrar(self, texto):
        self.acoes.appendleft({"hora": f"{datetime.datetime.now():%H:%M:%S}", "texto": str(texto)[:200]})
        log.info("Notebook: %s", texto)

    def continuar(self):
        """Segura o agente enquanto está pausado. False = o senhor mandou parar."""
        while self.pausado.is_set() and not self.parar.is_set():
            time.sleep(0.2)
        return not self.parar.is_set()

    def correcoes_novas(self):
        novas = []
        while not self.correcoes.empty():
            novas.append(self.correcoes.get_nowait())
        return novas

    def estado(self):
        return {"controlando": self.controlando, "pausado": self.pausado.is_set(), "tarefa": self.tarefa,
                "acoes": list(self.acoes)[:30]}


# ---------- o agente agindo aqui ----------
class AlvoNotebook:
    """Adaptador para o agente_tela: a mesma interface do módulo tela, mas pelo ControleReal (que minimiza o
    Braga quando ele está na frente do clique) e registrando cada ação."""

    def __init__(self, captura, controle, sessao):
        self.captura, self.controle, self.sessao = captura, controle, sessao
        self._largura, self._altura = 1, 1

    def preparar(self):
        self.controle.preparar()

    def capturar(self):
        self.captura.quadro()  # mantém a primeira pessoa ligada (Braga por cima e fora da foto) durante a tarefa
        imagem = self.captura.foto(tela.LARGURA_MODELO, com_mouse=False)
        imagem.save(tela.CAPTURA)
        self._largura, self._altura = imagem.width, imagem.height
        return tela.CAPTURA, imagem.width, imagem.height

    def clicar(self, x, y, duplo=False, botao="left"):
        tipo = "Clique duplo" if duplo else "Clique direito" if botao == "right" else "Clique"
        self.sessao.registrar(f"{tipo} em {x},{y}")
        self.controle.clicar(x / self._largura, y / self._altura, botao, duplo)

    def digitar(self, texto):
        self.sessao.registrar(f"Digitou: {texto[:60]}")
        self.controle.digitar(texto)

    def tecla(self, nome):
        self.sessao.registrar(f"Tecla: {nome}")
        self.controle.tecla(nome)

    def rolar(self, cliques):
        self.sessao.registrar(f"Rolou {cliques}")
        self.controle.rolar(cliques)


class AlvoVirtual:
    """O notebook VIRTUAL: o agente age no navegador do Braga (o Edge invisível), então nada abre no PC de verdade.
    Tem as mesmas funções do navegador.py, mais a sessão do notebook (pausar, parar, corrigir, confirmar)."""

    def __init__(self, sessao):
        self.sessao = sessao

    def __getattr__(self, nome):
        import navegador
        return getattr(navegador, nome)


captura = CapturaTela()
controle = ControleReal(captura)
sessao = Sessao()
alvo = AlvoNotebook(captura, controle, sessao)
alvo_virtual = AlvoVirtual(sessao)


def atalho_parar(ao_parar=None):
    """Ctrl+Alt+Q em qualquer janela para o Braga no PC (como o botão PARAR). Usa o RegisterHotKey do Windows,
    que só avisa desse atalho: não é um gancho que lê o teclado inteiro (antivírus não reclamam)."""
    def vigiar():
        MOD_ALT, MOD_CONTROL, MOD_NOREPEAT, WM_HOTKEY = 0x1, 0x2, 0x4000, 0x312
        if not user32.RegisterHotKey(None, 1, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, ord("Q")):
            log.warning("Atalho Ctrl+Alt+Q indisponível (outro programa já usa)")
            return
        mensagem = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(mensagem), None, 0, 0) > 0:
            if mensagem.message == WM_HOTKEY:
                sessao.parar.set()
                sessao.pausado.clear()
                sessao.registrar("Parado pelo senhor: Ctrl+Alt+Q")
                if ao_parar:
                    try:
                        ao_parar()
                    except Exception:
                        log.debug("Ctrl+Alt+Q: falha ao avisar a interface", exc_info=True)

    threading.Thread(target=vigiar, daemon=True, name="atalho-parar").start()


def cursor():
    """Onde está o mouse de verdade, de 0 a 1 na tela principal (o avatar do Braga move a mão junto)."""
    m = captura.tamanho()
    ponto = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(ponto))
    return [round(min(1, max(0, (ponto.x - m["left"]) / m["width"])), 4),
            round(min(1, max(0, (ponto.y - m["top"]) / m["height"])), 4)]


def info():
    m = captura.tamanho()
    return {"largura": m["width"], "altura": m["height"], "freio": controle.freio}


def executar(tipo, x=None, y=None, valor=None):
    """Ações do senhor na mini tela do notebook. x e y vão de 0 a 1."""
    if tipo == "clicar":
        controle.clicar(x, y)
    elif tipo == "duplo":
        controle.clicar(x, y, duplo=True)
    elif tipo == "direito":
        controle.clicar(x, y, botao="right")
    elif tipo == "mover":
        controle.mover(x, y)
    elif tipo == "deslizar":
        controle.deslizar(*(valor or (0, 0)))
        return {"ok": True}  # o dedo manda muitos destes: sem registro nem estado, para não pesar
    elif tipo == "tocar":
        controle.tocar(valor if valor in ("left", "right") else "left")
    elif tipo == "tocar_duplo":
        controle.tocar(duplo=True)
    elif tipo == "rolar":
        passos = round(float(valor or 0) / 100)
        controle.rolar(-(passos or (1 if float(valor or 0) > 0 else -1)))
    elif tipo == "digitar":
        controle.focar_alvo()
        controle.digitar(valor or "")
    elif tipo == "tecla":
        controle.focar_alvo()
        controle.tecla(valor or "enter")
    elif tipo == "pausar":
        sessao.pausado.set()
        sessao.registrar("Pausado pelo senhor")
    elif tipo == "retomar":
        sessao.pausado.clear()
        sessao.registrar("Retomado")
    elif tipo == "parar":
        sessao.parar.set()
        sessao.pausado.clear()
        sessao.registrar("Parado pelo senhor")
    elif tipo == "corrigir" and valor:
        sessao.correcoes.put(str(valor))
        sessao.registrar(f"Correção: {valor}")
    elif tipo == "freio":
        controle.freio = bool(valor)
        sessao.registrar("Freio do canto " + ("ligado" if controle.freio else "desligado"))
    if tipo in ("clicar", "duplo", "direito", "tecla", "tocar", "tocar_duplo"):
        sessao.registrar(f"Senhor: {tipo}" + (f" {valor}" if tipo == "tecla" else ""))
    elif tipo == "digitar":
        sessao.registrar(f"Senhor digitou: {str(valor)[:40]}")
    return sessao.estado()


if __name__ == "__main__":
    tela.preparar()
    numeros = set()
    inicio = time.time()
    while time.time() - inicio < 4:
        captura.quadro()
        numeros.add(captura.numero)
        time.sleep(0.03)
    print(f"{len(numeros) / 4:.1f} quadros novos por segundo; tela {info()}; {len(captura.quadro() or b'')} bytes")
