"""Interface nativa PyQt6 do Braga."""
import base64
import logging
import os
import tempfile
import threading

from PyQt6.QtCore import QObject, QThread, Qt, QTimer, QUrl, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

log = logging.getLogger("jarvis")


class _Eventos(QObject):
    interface = pyqtSignal(str, tuple)
    arquivo = pyqtSignal(object)
    fechar = pyqtSignal()
    frente = pyqtSignal()


class JanelaBraga(QMainWindow):
    """Janela Qt compatível com os poucos métodos de janela usados pelo backend."""

    def __init__(self, jarvis, nome):
        super().__init__()
        self.jarvis = jarvis
        self.eventos = _Eventos(self)
        self.eventos.interface.connect(self._atualizar_interface)
        self.eventos.arquivo.connect(self._mostrar_dialogo_arquivo)
        self.eventos.fechar.connect(self.close)
        self.eventos.frente.connect(self._trazer_para_frente)
        self._arquivo_audio = None
        self._ultima_fala = ""
        self._estado = "ouvindo"
        self._microfone_ligado = True
        self._linhas_conversa = 0

        self.setWindowTitle(nome)
        self.setMinimumSize(900, 620)
        self.resize(1280, 820)
        self.setAcceptDrops(True)

        self.audio = QMediaPlayer(self)
        self.audio_saida = QAudioOutput(self)
        self.audio.setAudioOutput(self.audio_saida)
        self.audio.mediaStatusChanged.connect(self._estado_audio)
        self.audio.errorOccurred.connect(self._erro_audio)

        self._montar_interface()
        self._atalhos()

        self.atualizador = QTimer(self)
        self.atualizador.timeout.connect(self._atualizar_status_sistema)
        self.atualizador.start(3000)
        QTimer.singleShot(0, self._atualizar_status_sistema)

    def _montar_interface(self):
        self.setStyleSheet("""
            QMainWindow, QWidget#base { background: #07111f; color: #e8f0fc; }
            QWidget { font-family: "Segoe UI"; font-size: 14px; }
            QFrame#painel, QFrame#cartao {
                background: #0d1a2b; border: 1px solid #1d3047; border-radius: 16px;
            }
            QLabel#marca { color: #f4f8ff; font-size: 19px; font-weight: 700; letter-spacing: 2px; }
            QLabel#subtitulo, QLabel#suave { color: #8ea3bf; }
            QLabel#estado { color: #66a9ff; font-size: 12px; font-weight: 700; letter-spacing: 1px; }
            QLabel#titulo { color: #f3f7ff; font-size: 23px; font-weight: 600; }
            QLabel#orb {
                color: #dcecff; background: #12294a; border: 2px solid #438cf5;
                border-radius: 52px; font-size: 32px; font-weight: 700;
            }
            QPushButton {
                color: #dce8f8; background: #122238; border: 1px solid #263c57;
                border-radius: 10px; padding: 10px 14px; text-align: left;
            }
            QPushButton:hover { background: #193252; border-color: #438cf5; }
            QPushButton#primario {
                color: white; background: #2563eb; border: 1px solid #3b82f6;
                font-weight: 600; padding: 11px 18px;
            }
            QPushButton#primario:hover { background: #3478f6; }
            QPushButton#microfone {
                background: #102b29; border-color: #1c7665; color: #8ff3d5;
            }
            QPushButton#microfone[desligado="true"] {
                background: #321a20; border-color: #79343b; color: #ffb2b2;
            }
            QLineEdit {
                color: #f3f7ff; background: #091523; border: 1px solid #263c57;
                border-radius: 11px; padding: 13px 15px; selection-background-color: #2563eb;
            }
            QLineEdit:focus { border-color: #438cf5; }
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { width: 8px; background: transparent; }
            QScrollBar::handle:vertical { background: #2a405e; border-radius: 4px; min-height: 22px; }
        """)

        base = QWidget()
        base.setObjectName("base")
        self.setCentralWidget(base)
        raiz = QVBoxLayout(base)
        raiz.setContentsMargins(22, 20, 22, 20)
        raiz.setSpacing(16)

        topo = QHBoxLayout()
        identidade = QVBoxLayout()
        marca = QLabel("B.R.A.G.A.")
        marca.setObjectName("marca")
        identidade.addWidget(marca)
        subtitulo = QLabel("ASSISTENTE PESSOAL")
        subtitulo.setObjectName("subtitulo")
        identidade.addWidget(subtitulo)
        topo.addLayout(identidade)
        topo.addStretch(1)
        self.estado_topo = QLabel("INICIANDO")
        self.estado_topo.setObjectName("estado")
        topo.addWidget(self.estado_topo, alignment=Qt.AlignmentFlag.AlignRight)
        raiz.addLayout(topo)

        corpo = QHBoxLayout()
        corpo.setSpacing(16)
        raiz.addLayout(corpo, 1)

        lateral = QFrame()
        lateral.setObjectName("painel")
        lateral.setFixedWidth(224)
        menu = QVBoxLayout(lateral)
        menu.setContentsMargins(15, 18, 15, 16)
        menu.setSpacing(10)
        menu.addWidget(self._rotulo_secao("ATALHOS"))
        botoes = (
            ("Pesquisar na internet", "pesquisa no bing "),
            ("Criar lembrete", "me lembra "),
            ("Ajuda", "o que você pode fazer"),
        )
        for texto, comando in botoes:
            botao = QPushButton(texto)
            botao.clicked.connect(lambda _checked=False, c=comando: self._usar_atalho(c))
            menu.addWidget(botao)
        pdf = QPushButton("Juntar arquivos em PDF")
        pdf.clicked.connect(self.jarvis.gerar_pdf)
        menu.addWidget(pdf)

        menu.addSpacing(10)
        menu.addWidget(self._rotulo_secao("SISTEMA"))
        self.cpu = self._linha_sistema(menu, "Processador")
        self.ram = self._linha_sistema(menu, "Memória")
        self.disco = self._linha_sistema(menu, "Armazenamento")
        self.bateria = self._linha_sistema(menu, "Bateria")
        menu.addStretch(1)
        self.microfone = QPushButton("Microfone ativo")
        self.microfone.setObjectName("microfone")
        self.microfone.clicked.connect(self._alternar_microfone)
        menu.addWidget(self.microfone)
        corpo.addWidget(lateral)

        principal = QVBoxLayout()
        principal.setSpacing(14)
        corpo.addLayout(principal, 1)

        assistente = QFrame()
        assistente.setObjectName("cartao")
        assistente_layout = QHBoxLayout(assistente)
        assistente_layout.setContentsMargins(24, 18, 24, 18)
        assistente_layout.setSpacing(18)
        identificador = QLabel("3D")
        identificador.setObjectName("orb")
        identificador.setObjectName("orb")
        identificador.setAlignment(Qt.AlignmentFlag.AlignCenter)
        identificador.setFixedSize(94, 94)
        assistente_layout.addWidget(identificador)
        texto_assistente = QVBoxLayout()
        titulo = QLabel("Olá. Como posso ajudar?")
        titulo.setObjectName("titulo")
        texto_assistente.addWidget(titulo)
        self.descricao_estado = QLabel("Estou pronto para ouvir seu comando.")
        self.descricao_estado.setObjectName("suave")
        self.descricao_estado.setWordWrap(True)
        texto_assistente.addWidget(self.descricao_estado)
        self.atividade = QLabel("")
        self.atividade.setObjectName("suave")
        self.atividade.setWordWrap(True)
        texto_assistente.addWidget(self.atividade)
        self.status_modelo = QLabel("Modelo GLB · sem texturas, rig ou animações")
        self.status_modelo.setObjectName("suave")
        texto_assistente.addWidget(self.status_modelo)
        ver_modelo = QPushButton("Abrir visualização 3D")
        ver_modelo.setObjectName("primario")
        ver_modelo.clicked.connect(self._abrir_visualizador)
        texto_assistente.addWidget(ver_modelo, alignment=Qt.AlignmentFlag.AlignLeft)
        assistente_layout.addLayout(texto_assistente, 1)
        principal.addWidget(assistente)

        conversa = QFrame()
        conversa.setObjectName("painel")
        conversa_layout = QVBoxLayout(conversa)
        conversa_layout.setContentsMargins(18, 16, 18, 16)
        conversa_layout.setSpacing(10)
        cabecalho = QHBoxLayout()
        cabecalho.addWidget(self._rotulo_secao("CONVERSA"))
        cabecalho.addStretch(1)
        self.limpar = QPushButton("Limpar")
        self.limpar.setMaximumWidth(85)
        self.limpar.clicked.connect(self._limpar_conversa)
        cabecalho.addWidget(self.limpar)
        conversa_layout.addLayout(cabecalho)

        self.historico = QWidget()
        self.historico_layout = QVBoxLayout(self.historico)
        self.historico_layout.setContentsMargins(4, 4, 4, 4)
        self.historico_layout.setSpacing(11)
        self.historico_layout.addStretch(1)
        self.scroll_conversa = QScrollArea()
        self.scroll_conversa.setWidgetResizable(True)
        self.scroll_conversa.setWidget(self.historico)
        conversa_layout.addWidget(self.scroll_conversa, 1)
        principal.addWidget(conversa, 1)

        entrada = QHBoxLayout()
        entrada.setSpacing(9)
        self.campo = QLineEdit()
        self.campo.setPlaceholderText("Escreva um comando para o Braga…")
        self.campo.returnPressed.connect(self._enviar)
        entrada.addWidget(self.campo, 1)
        anexar = QPushButton("+ Anexar")
        anexar.clicked.connect(self._anexar)
        entrada.addWidget(anexar)
        enviar = QPushButton("Enviar")
        enviar.setObjectName("primario")
        enviar.clicked.connect(self._enviar)
        entrada.addWidget(enviar)
        principal.addLayout(entrada)

        rodape = QLabel("Aperte espaço para falar  ·  F11 para tela cheia")
        rodape.setObjectName("suave")
        raiz.addWidget(rodape)

    @staticmethod
    def _rotulo_secao(texto):
        label = QLabel(texto)
        label.setObjectName("estado")
        return label

    @staticmethod
    def _linha_sistema(layout, titulo):
        linha = QLabel(f"{titulo}   —")
        linha.setObjectName("suave")
        layout.addWidget(linha)
        return linha

    def _atalhos(self):
        self.atalho_espaco = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        self.atalho_espaco.activated.connect(self._falar_atalho)
        self.atalho_f11 = QShortcut(QKeySequence("F11"), self)
        self.atalho_f11.activated.connect(self.toggle_fullscreen)

    def _enviar(self):
        texto = self.campo.text().strip()
        if not texto:
            return
        self.campo.clear()
        self.jarvis.comando_texto(texto)

    def _usar_atalho(self, comando):
        self.campo.setText(comando)
        self.campo.setFocus()
        self.campo.setCursorPosition(len(comando))

    def _ouvir_agora(self):
        self.jarvis.ouvir_agora()

    def _falar_atalho(self):
        if not isinstance(QApplication.focusWidget(), QLineEdit):
            self._ouvir_agora()

    def _alternar_microfone(self):
        self._microfone_ligado = self.jarvis.alternar_microfone()
        self._atualizar_microfone(self._microfone_ligado)

    def _atualizar_microfone(self, ligado):
        self._microfone_ligado = ligado
        self.microfone.setText("Microfone ativo" if ligado else "Microfone pausado")
        self.microfone.setProperty("desligado", "false" if ligado else "true")
        self.microfone.style().unpolish(self.microfone)
        self.microfone.style().polish(self.microfone)

    def _anexar(self):
        self.jarvis.anexar()

    def _limpar_conversa(self):
        while self.historico_layout.count() > 0:
            item = self.historico_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.historico_layout.addStretch(1)
        self._linhas_conversa = 0

    def _adicionar_mensagem(self, autor, texto, tipo):
        if not texto:
            return
        if self.historico_layout.count() and self.historico_layout.itemAt(
                self.historico_layout.count() - 1).spacerItem():
            item = self.historico_layout.takeAt(self.historico_layout.count() - 1)
            del item
        grupo = QVBoxLayout()
        titulo = QLabel(autor)
        titulo.setObjectName("estado")
        mensagem = QLabel(texto)
        mensagem.setWordWrap(True)
        mensagem.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        mensagem.setStyleSheet(
            "color: #e8f0fc; background: #10233a; border-radius: 10px; padding: 11px;"
            if tipo == "usuario" else
            "color: #d5e3f6; background: #0b1726; border-radius: 10px; padding: 11px;"
        )
        grupo.addWidget(titulo)
        grupo.addWidget(mensagem)
        bloco = QWidget()
        bloco.setLayout(grupo)
        self.historico_layout.addWidget(bloco)
        self.historico_layout.addStretch(1)
        self._linhas_conversa += 1
        while self._linhas_conversa > 100:
            item = self.historico_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
            self._linhas_conversa -= 1
        QTimer.singleShot(
            0,
            lambda: self.scroll_conversa.verticalScrollBar().setValue(
                self.scroll_conversa.verticalScrollBar().maximum()
            ),
        )

    def _atualizar_status_sistema(self):
        try:
            status = self.jarvis.status()
        except Exception:
            log.exception("Falha ao atualizar o status do sistema")
            return
        self.cpu.setText(f"Processador   {status['cpu']}%")
        self.ram.setText(f"Memória   {status['ram']}%")
        self.disco.setText(f"Armazenamento   {status['disco']}%")
        bateria = status["bateria"]
        self.bateria.setText(
            "Bateria   —" if bateria is None else
            f"Bateria   {bateria}%{' · carregando' if status['carregando'] else ''}"
        )

    def _abrir_visualizador(self):
        try:
            import servidor
            servidor.iniciar()
            pagina = os.path.join(os.path.dirname(__file__), "interface", "avatar_qt.html")
            endereco = servidor.url_de(pagina)
            if not endereco:
                raise RuntimeError("A página do visualizador não está numa pasta servida.")
            if not QDesktopServices.openUrl(QUrl(endereco)):
                raise RuntimeError("O Windows não conseguiu abrir o navegador padrão.")
        except Exception:
            log.exception("Falha ao iniciar o visualizador do modelo 3D")
            self.status_modelo.setText("Não consegui abrir o visualizador 3D.")

    def _dispatch_interface(self, funcao, args):
        self.eventos.interface.emit(funcao, args)

    @pyqtSlot(str, tuple)
    def _atualizar_interface(self, funcao, args):
        if funcao == "estado":
            estado = str(args[0]) if args else "ouvindo"
            self._estado = estado
            nomes = {
                "ouvindo": ("PRONTO PARA OUVIR", "Estou pronto para ouvir seu comando."),
                "escutando": ("ESCUTANDO", "Pode falar. Estou ouvindo."),
                "pensando": ("PENSANDO", "Estou trabalhando no seu pedido."),
                "falando": ("FALANDO", "Estou respondendo."),
                "pausado": ("MICROFONE PAUSADO", "Ative o microfone para voltar a falar."),
                "sem-microfone": ("MICROFONE INDISPONÍVEL", "Não consegui acessar o microfone. Vou tentar novamente."),
                "offline": ("OFFLINE", "O assistente está temporariamente indisponível."),
            }
            titulo, descricao = nomes.get(estado, (estado.upper(), estado))
            self.estado_topo.setText(titulo)
            self.descricao_estado.setText(descricao)
        elif funcao == "ouviu" and args:
            self.atividade.setText(f"Entendi: {args[0]}")
        elif funcao == "voceDisse" and args:
            self._adicionar_mensagem("Você", str(args[0]), "usuario")
        elif funcao == "falaTexto" and args:
            self._ultima_fala = str(args[0])
            self._adicionar_mensagem("Braga", self._ultima_fala, "braga")
        elif funcao == "atividade" and args:
            self.atividade.setText(str(args[0]))
        elif funcao == "tarefa":
            titulo = str(args[0]) if args and args[0] else ""
            pedido = str(args[1]) if len(args) > 1 and args[1] else ""
            self.atividade.setText(f"{titulo}: {pedido}" if titulo and pedido else titulo or pedido)
        elif funcao == "nota" and args:
            self.atividade.setText(str(args[0]))
        elif funcao == "micEstado" and args:
            self._atualizar_microfone(bool(args[0]))
        elif funcao == "tocarAudio" and args:
            self._tocar_audio(str(args[0]))
        elif funcao in ("abrirAba", "abrirNavegador", "abrirNotebook"):
            if funcao == "abrirAba" and len(args) > 1:
                endereco = args[3] or args[1] if len(args) > 3 else args[1]
                if endereco:
                    QDesktopServices.openUrl(QUrl(str(endereco)))
            else:
                self._adicionar_mensagem(
                    "Braga",
                    "O mini navegador e o mini notebook ainda não foram migrados para a interface PyQt6.",
                    "braga",
                )
        elif funcao == "comandoProposto" and len(args) > 1:
            frases = ", ".join(args[0]) if args[0] else "novo comando"
            self._adicionar_mensagem(
                "Braga",
                f"Novo comando: {frases}\n{args[1]}\nDiga 'sim' para confirmar ou 'não' para cancelar.",
                "braga",
            )
        elif funcao == "biblioteca" and args:
            itens = args[0]
            resumo = "Biblioteca atualizada."
            if itens:
                resumo = "Arquivos: " + ", ".join(item.get("nome", "Arquivo") for item in itens[:5])
            self.atividade.setText(resumo)
        elif funcao == "aviso" and args:
            self._adicionar_mensagem("Aviso", str(args[0]), "braga")
        elif funcao == "bip":
            QApplication.beep()

    def _tocar_audio(self, conteudo):
        try:
            dados = base64.b64decode(conteudo, validate=True)
            if self._arquivo_audio and os.path.exists(self._arquivo_audio):
                os.remove(self._arquivo_audio)
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as arquivo:
                arquivo.write(dados)
                self._arquivo_audio = arquivo.name
            self.audio.setSource(QUrl.fromLocalFile(self._arquivo_audio))
            self.audio.play()
        except (OSError, ValueError):
            log.exception("Não foi possível iniciar o áudio do Braga")
            self.jarvis.fim_fala()

    def _estado_audio(self, estado):
        if estado == QMediaPlayer.MediaStatus.EndOfMedia:
            self.jarvis.fim_fala()
            self._apagar_audio()

    def _erro_audio(self, erro, mensagem):
        if erro != QMediaPlayer.Error.NoError:
            log.warning("Falha na reprodução de áudio Qt: %s", mensagem)
            self.atividade.setText("O áudio não pôde ser reproduzido.")
            self.jarvis.fim_fala()
            self._apagar_audio()

    def _apagar_audio(self):
        if self._arquivo_audio and os.path.exists(self._arquivo_audio):
            try:
                os.remove(self._arquivo_audio)
            except OSError:
                log.warning("Não foi possível remover o áudio temporário %s", self._arquivo_audio)
            self._arquivo_audio = None

    def create_file_dialog(self, _dialog_type=None, allow_multiple=False, **_kwargs):
        pedido = {"event": threading.Event(), "result": [], "multiple": allow_multiple}
        if QThread.currentThread() == self.thread():
            self._mostrar_dialogo_arquivo(pedido)
        else:
            self.eventos.arquivo.emit(pedido)
            if not pedido["event"].wait(timeout=300):
                raise RuntimeError("A janela de seleção de arquivos não respondeu.")
        return pedido["result"]

    def abrir_url(self, endereco):
        if not QDesktopServices.openUrl(QUrl(str(endereco))):
            log.warning("O navegador padrão não conseguiu abrir %s", endereco)
            return False
        return True

    @pyqtSlot(object)
    def _mostrar_dialogo_arquivo(self, pedido):
        try:
            if pedido["multiple"]:
                pedido["result"] = QFileDialog.getOpenFileNames(self, "Selecionar arquivos")[0]
            else:
                caminho = QFileDialog.getOpenFileName(self, "Selecionar arquivo")[0]
                pedido["result"] = [caminho] if caminho else []
        finally:
            pedido["event"].set()

    def restore(self):
        if QThread.currentThread() == self.thread():
            self.showNormal()
        else:
            self.eventos.frente.emit()

    def show(self):
        if QThread.currentThread() == self.thread():
            super().show()
        else:
            self.eventos.frente.emit()

    @pyqtSlot()
    def _trazer_para_frente(self):
        self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()

    def destroy(self):
        self.eventos.fechar.emit()

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def evaluate_js(self, _script):
        return None

    def dragEnterEvent(self, evento):
        if evento.mimeData().hasUrls():
            evento.acceptProposedAction()

    def dropEvent(self, evento):
        arquivos = [url.toLocalFile() for url in evento.mimeData().urls() if url.isLocalFile()]
        for caminho in arquivos:
            try:
                self.jarvis._guardar(
                    lambda c=caminho: __import__("biblioteca").adicionar_arquivo(c),
                    os.path.basename(caminho),
                )
            except Exception:
                log.exception("Falha ao adicionar arquivo arrastado: %s", caminho)
        evento.acceptProposedAction()

    def closeEvent(self, evento):
        self.atualizador.stop()
        self.audio.stop()
        self._apagar_audio()
        if self.jarvis._janela is self:
            self.jarvis._janela = None
        evento.accept()
        QApplication.instance().quit()


def iniciar(jarvis, nome):
    app = QApplication.instance() or QApplication([])
    app.setApplicationName(nome)
    janela = JanelaBraga(jarvis, nome)
    janela.showMaximized()
    jarvis._janela = janela
    threading.Thread(target=jarvis._vigiar_github, daemon=True).start()
    threading.Thread(target=jarvis._vigiar_respostas, daemon=True).start()
    QTimer.singleShot(0, jarvis.pronto)
    app.exec()
