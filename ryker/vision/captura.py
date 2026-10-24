"""Captura da tela do Windows com dois motores, para medir e escolher (Fase 1).

- "mss":   copia a tela pelo GDI. Simples e confiável; é o que o mini notebook usa hoje (desktop/notebook.py).
- "dxcam": Desktop Duplication API (DXGI). Só entrega quando a tela muda e gasta pouco processador.

    with Captura("dxcam") as cap:
        imagem = cap.foto()          # PIL.Image RGB, ou None se a tela não mudou (só no dxcam)

As duas devolvem a tela principal inteira, em pixels reais. Os pacotes são importados só quando usados: o Braga
funciona sem o dxcam instalado.
"""
import ctypes
import logging

from PIL import Image

log = logging.getLogger("jarvis")
MOTORES = ("mss", "dxcam")


def _dpi_real():
    """Sem isto, numa tela com escala (125%, 150%) o Windows entrega a imagem e as coordenadas reduzidas."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass


class Captura:
    def __init__(self, motor="mss"):
        if motor not in MOTORES:
            raise ValueError(f"motor desconhecido: {motor}")
        self.motor = motor
        self._sct = None
        self._cam = None
        self.monitor = None

    def __enter__(self):
        _dpi_real()
        if self.motor == "mss":
            import mss
            self._sct = getattr(mss, "MSS", mss.mss)()
            self.monitor = dict(self._sct.monitors[1])
        else:
            import dxcam
            self._cam = dxcam.create(output_color="RGB")
            altura, largura = self._cam.height, self._cam.width
            self.monitor = {"left": 0, "top": 0, "width": largura, "height": altura}
        return self

    def __exit__(self, *erro):
        if self._sct:
            self._sct.close()
        if self._cam:
            try:
                self._cam.release()
            except Exception:
                pass
            del self._cam
        return False

    def foto(self):
        """Tela principal como PIL.Image RGB. No dxcam, None quando nada mudou desde a última foto."""
        if self.motor == "mss":
            bruta = self._sct.grab(self.monitor)
            return Image.frombytes("RGB", bruta.size, bruta.bgra, "raw", "BGRX")
        quadro = self._cam.grab()
        return None if quadro is None else Image.fromarray(quadro)
