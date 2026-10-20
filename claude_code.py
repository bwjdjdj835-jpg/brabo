"""Ponte entre o Jarvis e o Claude Code (o comando `claude` instalado no notebook)."""
import glob
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import threading
import unicodedata

import biblioteca
import memoria

PASTA = os.path.dirname(os.path.abspath(__file__))
PROJETOS = os.path.join(PASTA, "projetos")
ULTIMO = os.path.join(PROJETOS, "ultimo_projeto.txt")
LIMITE_APP = 25 * 60  # segundos
LIMITE_CONVERSA = 90

# O que o Claude Code pode fazer sozinho quando cria um app.
# Ele trabalha só dentro da pasta do projeto; qualquer outra coisa é negada.
FERRAMENTAS_APP = [
    # Sem "Write"/"Edit" aqui de propósito: o modo acceptEdits já libera edições só dentro da pasta do projeto.
    "Read", "Glob", "Grep", "TodoWrite", "WebSearch", "WebFetch",
    "Bash(npm:*)", "Bash(npx:*)", "Bash(node:*)", "Bash(mkdir:*)", "Bash(ls:*)", "Bash(cd:*)",
    "Bash(cp:*)",  # para trazer logos e imagens da biblioteca para o projeto
]

USAR_BIBLIOTECA = (
    "Junto com o pedido vem a biblioteca do usuário: os dados dele e referências que ele mandou "
    "(fotos de interfaces, logos, documentos, links), já resumidas. Antes de começar, abra com Read os itens "
    "relevantes para o pedido e siga o estilo, as cores e os dados deles. Para usar uma imagem ou logo da "
    "biblioteca no projeto, copie o arquivo para dentro desta pasta com cp. "
)

INSTRUCOES_APP = (
    "Você está sendo acionado pelo JARVIS, o assistente de voz do usuário. "
    "Construa o que foi pedido nesta pasta, completo e funcionando, sem fazer perguntas. "
    "Prefira um site estático (index.html com CSS e JS) que abra direto no navegador, "
    "a não ser que o pedido realmente precise de outra coisa. Capriche no visual. "
    + USAR_BIBLIOTECA +
    "Não mexa em nada fora desta pasta. Ao terminar, responda com uma ou duas frases curtas "
    "em português do Brasil, sem markdown, dizendo o que você fez."
)

STUDIO = r"C:\Program Files\Android\Android Studio"
SDK_ANDROID = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Android", "Sdk")
LIMITE_ANDROID = 45 * 60

FERRAMENTAS_ANDROID = FERRAMENTAS_APP + [
    "Bash(gradle:*)", "Bash(./gradlew:*)", "Bash(gradlew:*)", "Bash(gradlew.bat:*)",
    "Bash(java:*)", "Bash(cat:*)", "Bash(find:*)",
]

INSTRUCOES_ANDROID = (
    "Você está sendo acionado pelo JARVIS, o assistente de voz do usuário. "
    "Crie nesta pasta um app Android nativo em Kotlin, completo e funcionando, pronto para abrir no "
    "Android Studio, sem fazer perguntas. Use sempre a ferramenta Bash para comandos. "
    "O ambiente já tem: JAVA_HOME (Java do Android Studio), ANDROID_HOME = " + SDK_ANDROID.replace("\\", "/") + " "
    "(plataformas android-34 a android-36 instaladas) e o comando gradle no PATH. "
    "Para não depender de downloads, prefira as versões do Android Gradle Plugin e do Kotlin que já estão em "
    "~/.gradle/caches/modules-2/files-2.1. Escreva o local.properties com sdk.dir, rode `gradle wrapper` "
    "e depois `./gradlew assembleDebug`, corrigindo os erros até o APK ser gerado. "
    + USAR_BIBLIOTECA +
    "Não mexa em nada fora desta pasta. Ao terminar, responda com uma ou duas frases curtas em português "
    "do Brasil, sem markdown, dizendo o que o app faz e se o APK foi gerado."
)

INSTRUCOES_CONVERSA = (
    "Você é o JARVIS, assistente pessoal por voz do usuário, a quem você chama de senhor. "
    "Junto com cada pedido vem a memória do Jarvis: a conversa recente e os projetos que ele já criou, "
    "com as pastas e os arquivos gerados. Use essa memória como se fosse sua, porque foi você que fez. "
    "Se perguntarem onde está um arquivo, diga o caminho exato que está na memória. "
    "Você pode ler as pastas dos projetos para conferir algo, mas não altere nada. "
    "Sua resposta será falada em voz alta: responda em português do Brasil, em no máximo "
    "três frases curtas, sem markdown, sem listas e sem emojis."
)

IGNORAR = {
    "jarvis", "cria", "criar", "crie", "faz", "faca", "fazer", "monta", "montar", "gera", "gerar",
    "desenvolve", "desenvolver", "constroi", "construir", "um", "uma", "o", "a", "os", "as", "de",
    "do", "da", "dos", "das", "com", "para", "pra", "pro", "me", "e", "no", "na", "por", "favor",
}

log = logging.getLogger("jarvis")
_ocupado = threading.Lock()


def _executavel():
    """Acha o claude.exe (o atalho claude.cmd do npm atrapalha alguns parâmetros)."""
    caminho = shutil.which("claude")
    if caminho and caminho.lower().endswith((".cmd", ".ps1")):
        exe = os.path.join(os.path.dirname(caminho), "node_modules", "@anthropic-ai", "claude-code", "bin", "claude.exe")
        if os.path.exists(exe):
            return exe
    return caminho


def disponivel():
    return _executavel() is not None


def ocupado():
    return _ocupado.locked()


def ultimo_projeto():
    try:
        with open(ULTIMO, encoding="utf-8") as arquivo:
            pasta = arquivo.read().strip()
        return pasta if os.path.isdir(pasta) else None
    except OSError:
        return None


def eh_android(pasta):
    return any(os.path.exists(os.path.join(pasta, nome)) for nome in ("settings.gradle.kts", "settings.gradle"))


def apk_de(pasta):
    """Caminho do APK gerado, se existir."""
    apk = os.path.join(pasta, "app", "build", "outputs", "apk", "debug", "app-debug.apk")
    return apk if os.path.exists(apk) else None


def _ambiente_android():
    """Variáveis para o Claude conseguir compilar: Java do Android Studio, SDK e Gradle no PATH."""
    ambiente = dict(os.environ)
    java = os.path.join(STUDIO, "jbr")
    caminhos = [os.path.join(java, "bin"), os.path.join(SDK_ANDROID, "platform-tools")]
    dists = os.path.join(os.path.expanduser("~"), ".gradle", "wrapper", "dists")
    gradles = sorted(glob.glob(os.path.join(dists, "gradle-*", "*", "gradle-*", "bin")))
    if gradles:
        caminhos.insert(0, gradles[-1])
    ambiente.update(JAVA_HOME=java, ANDROID_HOME=SDK_ANDROID, ANDROID_SDK_ROOT=SDK_ANDROID)
    ambiente["PATH"] = os.pathsep.join(caminhos + [ambiente.get("PATH", "")])
    return ambiente


def _nome_projeto(pedido):
    texto = unicodedata.normalize("NFD", pedido.lower())
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    palavras = [p for p in re.findall(r"[a-z0-9]+", texto) if p not in IGNORAR]
    base = "-".join(palavras[:4]) or "app"
    nome, n = base, 2
    while os.path.exists(os.path.join(PROJETOS, nome)):
        nome, n = f"{base}-{n}", n + 1
    return nome


def _descrever(ferramenta):
    nome = ferramenta.get("name", "")
    entrada = ferramenta.get("input") or {}
    arquivo = os.path.basename(entrada.get("file_path") or entrada.get("path") or "")
    if nome == "Write":
        return f"Criando {arquivo}"
    if nome in ("Edit", "MultiEdit"):
        return f"Editando {arquivo}"
    if nome == "Read":
        return f"Lendo {arquivo}"
    if nome == "Bash":
        return "Executando " + (entrada.get("command") or "")[:70]
    if nome in ("Glob", "Grep"):
        return "Procurando nos arquivos"
    if nome == "TodoWrite":
        return "Planejando as etapas"
    if nome in ("WebSearch", "WebFetch"):
        return "Pesquisando na internet"
    return f"Usando {nome}"


def _rodar(pedido, pasta, argumentos, limite, ao_evento=None, ambiente=None):
    """Roda o Claude Code e devolve (deu_certo, resposta_final)."""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as instrucoes:
        instrucoes.write(argumentos.pop("instrucoes"))
    comando = [
        _executavel(), "-p",
        "--output-format", "stream-json", "--verbose",
        "--append-system-prompt-file", instrucoes.name,
        *argumentos["extras"],
    ]
    processo = subprocess.Popen(
        comando, cwd=pasta, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", creationflags=subprocess.CREATE_NO_WINDOW, env=ambiente,
    )
    relogio = threading.Timer(limite, processo.kill)
    relogio.start()
    resposta, deu_certo = "", False
    try:
        processo.stdin.write(pedido)
        processo.stdin.close()
        for linha in processo.stdout:
            try:
                evento = json.loads(linha)
            except json.JSONDecodeError:
                log.info("claude: %s", linha.strip()[:200])
                continue
            if evento.get("type") == "assistant" and ao_evento:
                for parte in evento.get("message", {}).get("content", []):
                    if parte.get("type") == "tool_use":
                        ao_evento(_descrever(parte))
            elif evento.get("type") == "result":
                resposta = (evento.get("result") or "").strip()
                deu_certo = not evento.get("is_error")
                if not deu_certo:
                    log.warning("Claude terminou com erro: %s", json.dumps(evento, ensure_ascii=False)[:500])
        processo.wait()
        if processo.returncode:
            log.warning("Claude saiu com código %s", processo.returncode)
    finally:
        relogio.cancel()
        os.unlink(instrucoes.name)
    return deu_certo and bool(resposta), resposta


def perguntar(pergunta):
    """Pergunta rápida: o Claude responde em poucas frases para o Jarvis falar."""
    pasta = os.path.join(PROJETOS, "_conversa")
    os.makedirs(pasta, exist_ok=True)
    deu_certo, resposta = _rodar(
        _com_memoria(pergunta), pasta,
        {"instrucoes": INSTRUCOES_CONVERSA,
         "extras": ["--model", "sonnet", "--max-turns", "8", "--add-dir", PROJETOS,
                    "--allowedTools", "Read", "Glob", "Grep", "WebSearch"]},
        LIMITE_CONVERSA,
    )
    if not deu_certo:
        import ia  # Claude fora do ar ou sem assinatura: tenta as IAs de reserva do .env
        reserva, _provedor = ia.responder(_com_memoria(pergunta), INSTRUCOES_CONVERSA)
        if reserva:
            return reserva
        return ("Não consegui uma resposta rápida do Claude, senhor. Se o senhor quer que eu construa algo, "
                "diga, por exemplo: cria um app de tarefas.")
    return resposta


def _com_memoria(pedido):
    partes = []
    lembrancas = memoria.contexto()
    if lembrancas:
        partes.append(f"<memoria_do_jarvis>\n{lembrancas}\n</memoria_do_jarvis>")
    referencias = biblioteca.contexto()
    if referencias:
        partes.append(f"<biblioteca_do_usuario>\n{referencias}\n</biblioteca_do_usuario>")
    if not partes:
        return pedido
    return "\n\n".join(partes) + f"\n\nPedido atual do usuário: {pedido}"


def analisar_material(pedido, instrucoes, ferramentas, limite=None):
    """Usado pela biblioteca e pela engenharia: o Claude abre um arquivo ou link e devolve um resumo."""
    return _rodar(
        pedido, biblioteca.BIBLIOTECA,
        {"instrucoes": instrucoes,
         "extras": ["--model", "sonnet", "--max-turns", "6", "--allowedTools", *ferramentas]},
        limite or LIMITE_CONVERSA * 2,
    )


def resumir(texto, instrucoes, limite=300):
    """O Claude lê um texto grande (ex.: legendas de vídeos) e devolve um resumo. Sem mexer em arquivos."""
    pasta = os.path.join(PROJETOS, "_conversa")
    os.makedirs(pasta, exist_ok=True)
    deu_certo, resposta = _rodar(
        texto, pasta,
        {"instrucoes": instrucoes, "extras": ["--model", "sonnet", "--max-turns", "2", "--allowedTools", "Read"]},
        limite,
    )
    if not deu_certo:
        import ia  # Claude fora do ar ou sem assinatura: tenta as IAs de reserva do .env
        reserva, _provedor = ia.responder(texto, instrucoes, limite=limite)
        if reserva:
            return True, reserva
    return deu_certo, resposta


def autoatualizar(pedido, instrucoes, ferramentas, ao_evento, limite=40 * 60):
    """O Claude mexe no código do próprio Jarvis. Quem chama faz o backup no git e confere depois."""
    with _ocupado:
        log.info("Autoatualização do Jarvis: %s", pedido[:300])
        return _rodar(
            pedido, PASTA,
            {"instrucoes": instrucoes,
             "extras": ["--permission-mode", "acceptEdits", "--allowedTools", *ferramentas]},
            limite, ao_evento,
        )


def passo_visao(pedido, instrucoes, pasta_foto):
    """Um passo do modo tela: o Claude lê a foto da pasta e devolve a próxima ação em texto (JSON)."""
    deu_certo, resposta = _rodar(
        pedido, pasta_foto,
        {"instrucoes": instrucoes,
         "extras": ["--model", "sonnet", "--max-turns", "3", "--allowedTools", "Read"]},
        120,
    )
    if not deu_certo:
        import ia  # reserva com visão (Gemini/OpenAI): a foto vai junto, já que elas não têm a ferramenta Read
        try:
            with open(os.path.join(pasta_foto, "jarvis_tela.png"), "rb") as arquivo:
                foto = arquivo.read()
        except OSError:
            foto = None
        reserva, _provedor = ia.responder(pedido + "\nA foto da tela vai anexada a esta mensagem.", instrucoes, foto)
        if reserva:
            return True, reserva
    return deu_certo, resposta


def _configuracao(tipo):
    """Instruções, ferramentas, limite de tempo e ambiente para cada tipo de projeto."""
    if tipo == "android":
        return INSTRUCOES_ANDROID, FERRAMENTAS_ANDROID, LIMITE_ANDROID, _ambiente_android()
    return INSTRUCOES_APP, FERRAMENTAS_APP, LIMITE_APP, None


def criar_app(pedido, ao_evento, tipo="web"):
    """Cria um projeto novo. Devolve (deu_certo, resposta, pasta)."""
    with _ocupado:
        pasta = os.path.join(PROJETOS, _nome_projeto(pedido))
        os.makedirs(pasta)
        with open(ULTIMO, "w", encoding="utf-8") as arquivo:
            arquivo.write(pasta)
        log.info("Criando app %s em %s: %s", tipo, pasta, pedido)
        instrucoes, ferramentas, limite, ambiente = _configuracao(tipo)
        deu_certo, resposta = _rodar(
            _com_memoria(pedido), pasta,
            {"instrucoes": instrucoes,
             "extras": ["--permission-mode", "acceptEdits", "--allowedTools", *ferramentas]},
            limite, ao_evento, ambiente,
        )
        return deu_certo, resposta, pasta


def editar_ultimo(pedido, ao_evento):
    """Continua o último projeto, com a mesma conversa do Claude. Devolve (deu_certo, resposta, pasta)."""
    pasta = ultimo_projeto()
    if not pasta:
        return False, "Ainda não criei nenhum app, senhor.", None
    with _ocupado:
        log.info("Editando app em %s: %s", pasta, pedido)
        instrucoes, ferramentas, limite, ambiente = _configuracao("android" if eh_android(pasta) else "web")
        deu_certo, resposta = _rodar(
            _com_memoria(pedido), pasta,
            {"instrucoes": instrucoes,
             "extras": ["--continue", "--permission-mode", "acceptEdits", "--allowedTools", *ferramentas]},
            limite, ao_evento, ambiente,
        )
        return deu_certo, resposta, pasta
