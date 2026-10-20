"""Modo fundo: a janela do Jarvis vira a camada de fundo da área de trabalho, atrás dos ícones.

Usa o mesmo truque do Windows para papel de parede animado: cria a janela "WorkerW" e encaixa a
janela do Jarvis nela. Não precisa de administrador, e os ícones e a barra de tarefas continuam por cima.
"""
import ctypes
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)

# Identificadores de janela têm 64 bits; sem declarar o tipo, o Python os corta e nada é encontrado.
user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowW.restype = wintypes.HWND
user32.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowExW.restype = wintypes.HWND
user32.SetParent.argtypes = [wintypes.HWND, wintypes.HWND]
user32.SetParent.restype = wintypes.HWND
user32.GetParent.argtypes = [wintypes.HWND]
user32.GetParent.restype = wintypes.HWND
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongW.restype = wintypes.LONG
user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
user32.SetWindowLongW.restype = wintypes.LONG
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.SetWindowPos.restype = wintypes.BOOL

TITULO = __import__("identidade").SIGLA
WM_SPAWN_WORKER = 0x052C
SMTO_NORMAL = 0
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
SWP_FRAMECHANGED = 0x0020
GWL_STYLE = -16
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000

_estilo_original = None


def achar_janela():
    """Acha a janela do Jarvis, mesmo que ela já esteja colada no fundo (aí é filha do Progman)."""
    janela = user32.FindWindowW(None, TITULO)
    if not janela:
        progman = user32.FindWindowW("Progman", None)
        janela = user32.FindWindowExW(progman, None, None, TITULO)
    return janela


def _workerw():
    """Janela de fundo da área de trabalho, onde a imagem do papel de parede é desenhada."""
    progman = user32.FindWindowW("Progman", None)
    if not progman:
        return None
    resultado = ctypes.c_void_p()
    user32.SendMessageTimeoutW(progman, WM_SPAWN_WORKER, 0, 0, SMTO_NORMAL, 1000, ctypes.byref(resultado))

    alvo = [None]
    tipo = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def ao_encontrar(hwnd, _):
        # a janela que tem os ícones (SHELLDLL_DefView) fica por cima; queremos a WorkerW logo abaixo dela
        if user32.FindWindowExW(hwnd, None, "SHELLDLL_DefView", None):
            alvo[0] = user32.FindWindowExW(None, hwnd, "WorkerW", None)
        return True

    user32.EnumWindows(tipo(ao_encontrar), 0)
    return alvo[0]


HWND_BOTTOM = wintypes.HWND(1)


def ancorar(hwnd):
    """Coloca a janela do Jarvis no fundo, cobrindo a tela inteira. Devolve True se conseguiu."""
    global _estilo_original
    # Em algumas versões do Windows os ícones ficam direto no Progman; nesse caso o Jarvis entra nele.
    trabalhador = _workerw() or user32.FindWindowW("Progman", None)
    if not trabalhador:
        return False
    estilo = user32.GetWindowLongW(hwnd, GWL_STYLE)
    _estilo_original = estilo
    # tira a borda e a barra de título, para ficar só o conteúdo
    user32.SetWindowLongW(hwnd, GWL_STYLE, estilo & ~(WS_CAPTION | WS_THICKFRAME))
    user32.SetParent(hwnd, trabalhador)
    largura, altura = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    # HWND_BOTTOM: fica atrás dos ícones, que são os filhos mais de cima
    user32.SetWindowPos(hwnd, HWND_BOTTOM, 0, 0, largura, altura, SWP_NOACTIVATE | SWP_SHOWWINDOW | SWP_FRAMECHANGED)
    return True


def soltar(hwnd):
    """Tira a janela do fundo e devolve a aparência de janela normal."""
    user32.SetParent(hwnd, None)
    if _estilo_original is not None:
        user32.SetWindowLongW(hwnd, GWL_STYLE, _estilo_original)
    user32.SetWindowPos(hwnd, None, 120, 80, 1280, 800, SWP_SHOWWINDOW | SWP_FRAMECHANGED)


def esta_no_fundo(hwnd):
    return bool(user32.GetParent(hwnd))
