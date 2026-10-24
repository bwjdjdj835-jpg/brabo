"""Controle de tela do Jarvis: tirar foto da tela, clicar, digitar e rolar.

É o "braço e o olho" do Jarvis. As decisões (o que clicar) são do laço do agente em agente_tela.py;
aqui ficam só as ações cruas. Freios de segurança:
- Atalho de pânico: jogue o mouse para o canto superior esquerdo da tela e tudo para na hora.
- Nunca digita senhas: quem decide (o agente) é instruído a não digitar senhas; aqui também há um
  limite de tamanho e nada é registrado em texto.
"""
import ctypes
import logging
import os
import time

from PIL import Image

PASTA = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # a pasta do Jarvis
CAPTURA = os.path.join(os.environ.get("TEMP", PASTA), "jarvis_tela.png")
LARGURA_MODELO = 1280  # a foto enviada ao Claude é reduzida para esta largura

log = logging.getLogger("jarvis")
_pronto = False
_escala = 1.0  # relação entre a foto reduzida e a tela real


def preparar():
    global _pronto
    if _pronto:
        return
    try:
        ctypes.windll.user32.SetProcessDPIAware()  # pixels da foto = pixels do clique
    except Exception:
        pass
    import pyautogui
    pyautogui.FAILSAFE = True   # mouse no canto superior esquerdo aborta tudo
    pyautogui.PAUSE = 0.3
    _pronto = True


def capturar():
    """Tira a foto da tela, reduz para o tamanho que o Claude lê e devolve (caminho, largura, altura)."""
    import mss
    with mss.mss() as sct:
        area = sct.monitors[1]
        imagem = sct.grab(area)
    img = Image.frombytes("RGB", imagem.size, imagem.bgra, "raw", "BGRX")
    global _escala
    if img.width > LARGURA_MODELO:
        _escala = img.width / LARGURA_MODELO
        img = img.resize((LARGURA_MODELO, round(img.height / _escala)))
    else:
        _escala = 1.0
    img.save(CAPTURA)
    return CAPTURA, img.width, img.height


def _real(x, y):
    """Converte coordenadas da foto reduzida para pixels reais da tela."""
    return round(x * _escala), round(y * _escala)


def clicar(x, y, duplo=False, botao="left"):
    import pyautogui
    rx, ry = _real(x, y)
    pyautogui.moveTo(rx, ry, duration=0.3)
    if duplo:
        pyautogui.doubleClick(rx, ry)
    else:
        pyautogui.click(rx, ry, button=botao)
    time.sleep(0.4)


def digitar(texto):
    import pyautogui
    if len(texto) > 500:
        texto = texto[:500]
    pyautogui.typewrite(texto, interval=0.02)
    time.sleep(0.2)


def tecla(nome):
    """Aperta uma tecla ou combinação, ex.: 'enter', 'tab', 'ctrl+a'."""
    import pyautogui
    partes = [p.strip() for p in nome.replace(" ", "").split("+") if p.strip()]
    if len(partes) > 1:
        pyautogui.hotkey(*partes)
    elif partes:
        pyautogui.press(partes[0])
    time.sleep(0.2)


def rolar(cliques):
    import pyautogui
    pyautogui.scroll(int(cliques))
    time.sleep(0.3)
