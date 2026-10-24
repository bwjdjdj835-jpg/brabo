"""Barramento de eventos do RYKER: os módulos avisam o que aconteceu sem se chamarem diretamente.

    from ryker.core import eventos
    eventos.assinar("acao", lambda e: print(e["acao"]))
    eventos.publicar("acao", acao="clicar", alvo={"nome": "Salvar"})

- Cada evento é um dicionário com "tipo", "hora" e os dados de quem publicou.
- Quem assina recebe o evento numa linha (thread) própria do barramento: quem publica nunca espera nem trava por
  causa de um assinante lento ou com erro (o erro vai para o log).
- assinar("*", ...) recebe todos os tipos (é assim que o quarto 3D vai ouvir tudo).
- Os últimos eventos ficam guardados (ultimos()) para quem chega depois, como o quarto aberto no meio de uma tarefa.

Tipos usados (ver o documento de arquitetura): objetivo, quadro, mudanca_tela, observacao, pensamento, plano, acao,
resultado, estado, parar.
"""
import collections
import datetime
import logging
import queue
import threading

log = logging.getLogger("jarvis")

TIPOS = {"objetivo", "quadro", "mudanca_tela", "observacao", "pensamento", "plano", "acao", "resultado", "estado",
         "parar"}


class Barramento:
    def __init__(self, guardar=200):
        self._assinantes = collections.defaultdict(list)
        self._trava = threading.Lock()
        self._fila = queue.Queue()
        self._recentes = collections.deque(maxlen=guardar)
        self._linha = None

    def assinar(self, tipo, funcao):
        """Chama funcao(evento) a cada evento desse tipo ("*" = todos). Devolve uma função que cancela a assinatura."""
        with self._trava:
            self._assinantes[tipo].append(funcao)

        def cancelar():
            with self._trava:
                if funcao in self._assinantes[tipo]:
                    self._assinantes[tipo].remove(funcao)
        return cancelar

    def publicar(self, tipo, **dados):
        if tipo not in TIPOS:
            log.warning("Evento de tipo desconhecido: %s", tipo)
        evento = {"tipo": tipo, "hora": datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3], **dados}
        if tipo != "quadro":  # quadros são muitos e grandes: não ficam guardados
            self._recentes.append(evento)
        self._iniciar()
        self._fila.put(evento)
        return evento

    def ultimos(self, tipo=None, quantidade=50):
        eventos = [e for e in self._recentes if tipo is None or e["tipo"] == tipo]
        return eventos[-quantidade:]

    def esperar_vazio(self, limite=2.0):
        """Para testes: espera os assinantes receberem tudo o que já foi publicado."""
        feito = threading.Event()
        self._fila.put(feito)
        return feito.wait(limite)

    def _iniciar(self):
        if self._linha is None:
            with self._trava:
                if self._linha is None:
                    self._linha = threading.Thread(target=self._entregar, daemon=True, name="ryker-eventos")
                    self._linha.start()

    def _entregar(self):
        while True:
            evento = self._fila.get()
            if isinstance(evento, threading.Event):
                evento.set()
                continue
            with self._trava:
                funcoes = list(self._assinantes.get(evento["tipo"], ())) + list(self._assinantes.get("*", ()))
            for funcao in funcoes:
                try:
                    funcao(evento)
                except Exception:
                    log.exception("Assinante do evento %s falhou", evento["tipo"])


_padrao = Barramento()
assinar = _padrao.assinar
publicar = _padrao.publicar
ultimos = _padrao.ultimos
esperar_vazio = _padrao.esperar_vazio
