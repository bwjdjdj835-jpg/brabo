"""Instalar programas pelo winget (o instalador oficial do Windows), sempre depois do "sim" do senhor.

"instala o VLC" -> o Braga procura no winget, escolhe o resultado certo (fonte winget, apelido ou nome exato),
diz qual achou e só instala com o "sim". A instalação roda escondida; se o instalador abrir alguma janela, ela
nasce atrás do Braga e aparece no mini notebook.
"""
import logging
import re
import shutil
import subprocess

log = logging.getLogger("jarvis")


def _winget():
    return shutil.which("winget")


def _rodar(argumentos, limite=120):
    resultado = subprocess.run([_winget(), *argumentos], capture_output=True, timeout=limite,
                               creationflags=subprocess.CREATE_NO_WINDOW)
    return resultado.returncode, resultado.stdout.decode("utf-8", "replace")


def buscar(nome, limite=8):
    """Resultados do winget: [{"nome", "id", "versao", "correspondencia", "origem"}]."""
    if not _winget():
        raise RuntimeError("o winget não está neste Windows")
    _, saida = _rodar(["search", nome, "--accept-source-agreements", "--count", str(limite)])
    linhas = [l.rstrip() for l in saida.replace("\r", "\n").split("\n")]
    cabecalho = next((i for i, l in enumerate(linhas) if re.search(r"\bID\b", l) and re.search(r"^\s*Nome|^\s*Name", l)), None)
    if cabecalho is None:
        return []
    titulo = linhas[cabecalho]
    colunas = [m.start() for m in re.finditer(r"\S+", titulo)]  # onde começa cada coluna
    resultados = []
    for linha in linhas[cabecalho + 2:]:
        if not linha.strip() or linha.startswith("<") or set(linha.strip()) <= {"-", " "}:
            continue
        partes = [linha[c:(colunas[i + 1] if i + 1 < len(colunas) else None)].strip() for i, c in enumerate(colunas)]
        if len(partes) < 3 or not partes[1]:
            continue
        resultados.append({"nome": partes[0], "id": partes[1], "versao": partes[2],
                           "correspondencia": partes[3] if len(partes) > 4 else "",
                           "origem": partes[-1]})
    return resultados


def melhor(resultados, nome):
    """O mais provável: da fonte winget (não da loja), com o apelido ou o nome iguais ao que o senhor falou."""
    alvo = nome.strip().lower()
    def nota(r):
        pontos = 0
        if r["origem"].lower() == "winget":
            pontos += 4
        if r["correspondencia"].lower() in (f"moniker: {alvo}", f"apelido: {alvo}"):
            pontos += 5
        if r["nome"].lower() == alvo:
            pontos += 6
        elif r["nome"].lower().startswith(alvo + " "):
            pontos += 3
        if alvo.replace(" ", "") in r["id"].lower().replace(".", ""):
            pontos += 2
        testes = r"\b(beta|dev|canary|nightly|preview|insider|alpha)\b"
        if re.search(testes, f"{r['nome']} {r['id']}", re.I) and not re.search(testes, alvo):
            pontos -= 6  # versão de teste só se o senhor pedir
        return pontos
    return max(resultados, key=nota) if resultados else None


def instalar(id_programa, ao_evento=None):
    """Instala pelo winget (chamar só depois do "sim"). Devolve (deu_certo, resumo)."""
    avisar = ao_evento or (lambda t: None)
    processo = subprocess.Popen(
        [_winget(), "install", "--id", id_programa, "-e", "--source", "winget", "--accept-source-agreements",
         "--accept-package-agreements", "--disable-interactivity"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    ultimas = []
    for bruta in processo.stdout:
        linha = bruta.decode("utf-8", "replace").strip()
        linha = re.sub(r"[█▒░\-\\|/]{3,}", "", linha).strip()  # tira as barras de progresso
        if len(linha) > 3:
            ultimas = (ultimas + [linha])[-4:]
            avisar(linha[:120])
    codigo = processo.wait(timeout=60 * 30)
    log.info("winget install %s -> %s | %s", id_programa, codigo, " / ".join(ultimas))
    return codigo == 0, " ".join(ultimas)[-200:]
