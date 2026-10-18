"""Servidor local da interface do Jarvis (só no próprio notebook: 127.0.0.1).

Abrir a interface por http em vez de file:// deixa o vídeo do YouTube tocar dentro das abas (o YouTube
recusa vídeos incorporados em páginas file://) e permite mostrar os sites criados em projetos/ numa aba.
Só as pastas de PASTAS_LIBERADAS são servidas; .env, memória, e-mail e o resto do Jarvis ficam de fora.
"""
import http.server
import logging
import os
import posixpath
import threading
import urllib.parse

PASTA = os.path.dirname(os.path.abspath(__file__))
PASTAS_LIBERADAS = {"interface", "projetos", "pdfs"}

log = logging.getLogger("jarvis")
_endereco = None


class _Manipulador(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PASTA, **kwargs)

    def _liberado(self):
        caminho = posixpath.normpath(urllib.parse.unquote(urllib.parse.urlsplit(self.path).path))
        partes = [p for p in caminho.split("/") if p]
        return bool(partes) and partes[0] in PASTAS_LIBERADAS and ".." not in partes

    def send_head(self):
        if not self._liberado():
            self.send_error(404)
            return None
        return super().send_head()

    def list_directory(self, path):
        self.send_error(404)  # nada de listar pastas
        return None

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")  # projetos alterados aparecem na hora
        super().end_headers()

    def log_message(self, formato, *args):
        pass  # não enche o jarvis.log com cada arquivo pedido


def iniciar():
    """Liga o servidor numa porta livre e devolve o endereço base (ex.: http://127.0.0.1:53012)."""
    global _endereco
    if _endereco:
        return _endereco
    servidor = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Manipulador)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    _endereco = f"http://127.0.0.1:{servidor.server_port}"
    log.info("Interface servida em %s", _endereco)
    return _endereco


def url_de(caminho):
    """Endereço http de um arquivo dentro das pastas liberadas, ou None se estiver fora delas."""
    if not _endereco:
        return None
    relativo = os.path.relpath(os.path.abspath(caminho), PASTA).replace("\\", "/")
    if relativo.split("/")[0] not in PASTAS_LIBERADAS:
        return None
    return f"{_endereco}/{urllib.parse.quote(relativo)}"
