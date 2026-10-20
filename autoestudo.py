"""Autoestudo do Jarvis: ele assiste (lê as legendas de) vídeos do YouTube, resume o que ensinam e,
se o usuário confirmar, pede ao Claude Code para se atualizar com as melhores ideias.

Os resumos ficam em melhorias/ideias/, que é também onde o Claude (no Claude Code) procura ideias quando
o usuário pede para melhorar o Jarvis. A autoatualização tem freios:
- antes, tudo é salvo num commit do git local (dá para voltar com `git log` / `git revert`);
- depois, o código é compilado e o app é importado; se quebrar, as mudanças são desfeitas na hora;
- senhas (.env), conversas e e-mail ficam fora do alcance; nada é instalado no Windows.
"""
import datetime
import glob
import logging
import os
import re
import subprocess
import sys
import unicodedata

import claude_code
import youtube

PASTA = os.path.dirname(os.path.abspath(__file__))
IDEIAS = os.path.join(PASTA, "melhorias", "ideias")
BACKLOG = os.path.join(PASTA, "melhorias", "BACKLOG.md")
MAX_VIDEOS = 10
CARACTERES_POR_VIDEO = 20_000
GIT = ["git", "-c", "user.name=Jarvis", "-c", "user.email=jarvis@localhost"]

INSTRUCOES_RESUMO = (
    "Você é o pesquisador do BRAGA, um assistente de voz para Windows feito em Python (pywebview, "
    "SpeechRecognition, edge-tts, Claude Code). O usuário quer que o Jarvis aprenda com vídeos do YouTube. "
    "Você vai receber as legendas de alguns vídeos. Escreva em português do Brasil, em markdown:\n"
    "1. A primeira linha exatamente assim: 'RESUMO_FALADO: ' seguido de no máximo duas frases curtas, sem markdown, "
    "para o Jarvis falar em voz alta.\n"
    "2. '## O que os vídeos ensinam': um resumo de cada vídeo em 2 a 4 linhas.\n"
    "3. '## Ideias para o Jarvis': uma lista de melhorias concretas e possíveis em Python no Windows, da mais "
    "valiosa para a menos, cada uma com uma linha de como fazer (biblioteca, API). Marque com (precisa de chave) "
    "as que dependem de conta paga ou chave de API. Não invente o que os vídeos não dizem."
)

INSTRUCOES_AUTO = (
    "Você é o Claude Code atualizando o próprio BRAGA, o assistente de voz do usuário, a pedido dele. "
    "A pasta atual é o código do Jarvis (app.py é o principal, comandos.py entende as frases, interface/index.html "
    "é a tela). Leia antes os arquivos que vai mexer e siga o estilo deles: português, nomes em português, "
    "comentários curtos. Regras:\n"
    "- Implemente no máximo 3 melhorias, as mais valiosas e seguras, que o Jarvis ainda NÃO tem. Pequeno e funcionando "
    "vale mais que grande e quebrado.\n"
    "- Não leia nem altere .env, memoria.json, email_config.json, telegram_ids.json, nem as pastas biblioteca/ e projetos/.\n"
    "- Não instale programas no Windows. Pacote Python só se for indispensável, com "
    "`.venv/Scripts/python.exe -m pip install`, e acrescente no requirements.txt.\n"
    "- Nada que envie mensagens, publique, compre, apague arquivos do usuário ou digite senhas sem pedir "
    "confirmação dele por voz (veja como _preparar_email usa self._pendente).\n"
    "- Teste antes de terminar: `.venv/Scripts/python.exe -c \"import py_compile,glob; "
    "[py_compile.compile(f, doraise=True) for f in glob.glob('*.py')]; import app\"` e teste as frases novas com "
    "comandos.executar. Não abra o app (ele já está aberto).\n"
    "- Anote o que fez na seção '## Feito' de melhorias/BACKLOG.md.\n"
    "Ao terminar, responda com uma ou duas frases curtas em português do Brasil, sem markdown, dizendo o que mudou: "
    "o Jarvis vai ler em voz alta."
)

FERRAMENTAS_AUTO = [
    "Read", "Glob", "Grep", "TodoWrite", "WebSearch", "WebFetch",
    "Bash(.venv/Scripts/python.exe:*)", "Bash(.venv\\Scripts\\python.exe:*)",
]

log = logging.getLogger("jarvis")


def _slug(texto):
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", texto).strip("-")[:40] or "videos"


def resumir_videos(busca, quantidade=5, ao_evento=None):
    """Lê as legendas dos vídeos da busca (ou playlist) e pede o resumo ao Claude.

    Devolve (frase para falar, caminho do resumo .md).
    """
    avisar = ao_evento or (lambda texto: None)
    quantidade = max(1, min(quantidade, MAX_VIDEOS))
    avisar("Procurando os vídeos")
    videos = youtube.listar(busca, quantidade)[:quantidade]
    if not videos:
        raise ValueError(f"Não achei vídeos para '{busca}'.")
    partes, lista, sem_legenda = [], [], 0
    for n, video in enumerate(videos, 1):
        avisar(f"Assistindo {n}/{len(videos)} · {video['titulo'][:60]}")
        try:
            titulo, descricao, texto = youtube.transcricao(video["url"])
        except Exception:
            log.warning("Falha ao ler o vídeo %s", video["url"], exc_info=True)
            titulo, descricao, texto = video["titulo"], "", ""
        if not texto:
            sem_legenda += 1
        lista.append(f"- [{titulo}]({video['url']})" + ("" if texto else " (sem legenda: só título e descrição)"))
        partes.append(f"### Vídeo {n}: {titulo}\nLink: {video['url']}\nDescrição: {descricao}\n\n"
                      f"Legenda:\n{texto[:CARACTERES_POR_VIDEO] or '(sem legenda)'}")
    if sem_legenda == len(videos):
        log.info("Nenhum vídeo de '%s' tinha legenda; o resumo usa só títulos e descrições", busca)

    avisar("Resumindo com o Claude")
    deu_certo, resposta = claude_code.resumir(
        f"Busca do usuário: {busca}\n\n" + "\n\n---\n\n".join(partes), INSTRUCOES_RESUMO)
    if not deu_certo:
        raise RuntimeError("O Claude não conseguiu resumir os vídeos agora.")

    falado = "Resumo pronto."
    primeira, _, corpo = resposta.partition("\n")
    if primeira.startswith("RESUMO_FALADO:"):
        falado, resposta = primeira.split(":", 1)[1].strip(), corpo.strip()

    os.makedirs(IDEIAS, exist_ok=True)
    agora = datetime.datetime.now()
    caminho = os.path.join(IDEIAS, f"{agora:%Y-%m-%d-%H%M}-{_slug(busca)}.md")
    with open(caminho, "w", encoding="utf-8") as arquivo:
        arquivo.write(f"# Ideias dos vídeos: {busca}\n\nGerado pelo Jarvis em {agora:%d/%m/%Y %H:%M}.\n\n"
                      f"## Vídeos\n" + "\n".join(lista) + f"\n\n{resposta}\n")
    _anotar_no_backlog(busca, caminho)
    log.info("Resumo dos vídeos salvo em %s", caminho)
    return falado, caminho


def _anotar_no_backlog(busca, caminho):
    titulo = "## Ideias dos vídeos (o Claude lê daqui para atualizar o Jarvis)"
    linha = f"- [ ] {os.path.relpath(caminho, os.path.dirname(BACKLOG)).replace(os.sep, '/')} ({busca})\n"
    try:
        with open(BACKLOG, encoding="utf-8") as arquivo:
            texto = arquivo.read()
    except OSError:
        texto = "# Backlog de melhorias do Jarvis\n"
    if titulo not in texto:
        texto = texto.rstrip("\n") + f"\n\n{titulo}\n"
    texto = texto.replace(titulo + "\n", titulo + "\n" + linha, 1)
    with open(BACKLOG, "w", encoding="utf-8") as arquivo:
        arquivo.write(texto)


def ultimo_resumo():
    resumos = sorted(glob.glob(os.path.join(IDEIAS, "*.md")))
    return resumos[-1] if resumos else None


def _git(*argumentos):
    return subprocess.run(GIT + list(argumentos), cwd=PASTA, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", creationflags=subprocess.CREATE_NO_WINDOW)


def _codigo_funciona():
    """Compila tudo e importa o app num processo separado (sem abrir a janela)."""
    teste = "import py_compile,glob; [py_compile.compile(f, doraise=True) for f in glob.glob('*.py')]; import app"
    resultado = subprocess.run([sys.executable, "-c", teste], cwd=PASTA, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=120,
                               creationflags=subprocess.CREATE_NO_WINDOW)
    if resultado.returncode:
        log.warning("Autoatualização quebrou o código:\n%s", resultado.stderr[-2000:])
    return resultado.returncode == 0


def atualizar_jarvis(pedido="", ao_evento=None):
    """O Jarvis pede ao Claude Code para se atualizar. Devolve (deu_certo, frase para falar)."""
    if not os.path.isdir(os.path.join(PASTA, ".git")):
        return False, "Não achei o backup do git na minha pasta, senhor, então não vou mexer no meu código."
    resumo = ultimo_resumo()
    if not resumo and not pedido:
        return False, ("Ainda não tenho ideias anotadas, senhor. Peça antes: resume os vídeos sobre como fazer "
                       "um Jarvis.")

    _git("add", "-A")
    _git("commit", "-q", "-m", "Backup antes da autoatualização do Jarvis")
    antes = _git("rev-parse", "HEAD").stdout.strip()

    tarefa = pedido or "Atualize o Jarvis com as melhores ideias do resumo."
    if resumo:
        tarefa += f"\n\nIdeias de referência (leia este arquivo): {os.path.relpath(resumo, PASTA)}"
    deu_certo, resposta = claude_code.autoatualizar(tarefa, INSTRUCOES_AUTO, FERRAMENTAS_AUTO, ao_evento)

    if not _codigo_funciona():
        _git("reset", "-q", "--hard", antes)
        _git("clean", "-fdq")  # tira só arquivos novos que o Claude criou (o resto estava no backup)
        return False, "A atualização quebrou meu código, senhor, então desfiz tudo. Os detalhes estão no registro."
    if not _git("status", "--porcelain").stdout.strip():
        return deu_certo, resposta or "Não mudei nada desta vez, senhor."
    _git("add", "-A")
    _git("commit", "-q", "-m", "Jarvis se atualizou: " + (resposta or tarefa)[:200])
    return True, (resposta or "Atualizei meu código, senhor.")
