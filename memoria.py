"""Memória do Jarvis: a conversa recente e os projetos criados, salvos em memoria.json.

Assim ele lembra do que aconteceu mesmo depois de fechar e abrir de novo.
"""
import datetime
import glob
import json
import logging
import os
import threading

PASTA = os.path.dirname(os.path.abspath(__file__))
ARQUIVO = os.path.join(PASTA, "memoria.json")
MAX_FALAS = 40       # quantas falas da conversa guardar
FALAS_NO_CONTEXTO = 16
PROJETOS_NO_CONTEXTO = 6

log = logging.getLogger("jarvis")
_trava = threading.Lock()


def _agora():
    return datetime.datetime.now().strftime("%d/%m %H:%M")


def _carregar():
    try:
        with open(ARQUIVO, encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except (OSError, json.JSONDecodeError):
        dados = {}
    dados.setdefault("conversa", [])
    dados.setdefault("projetos", [])
    return dados


def _salvar(dados):
    temporario = ARQUIVO + ".tmp"
    with open(temporario, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=1)
    os.replace(temporario, ARQUIVO)


def registrar_fala(quem, texto):
    with _trava:
        dados = _carregar()
        dados["conversa"].append({"quem": quem, "texto": texto, "hora": _agora()})
        dados["conversa"] = dados["conversa"][-MAX_FALAS:]
        _salvar(dados)


def arquivos_gerados(pasta):
    """Os arquivos que interessam ao usuário: APK, AAB, index.html e o LEIA-ME."""
    achados = []
    saidas = os.path.join(pasta, "app", "build", "outputs")
    for extensao in ("apk", "aab"):
        achados += sorted(glob.glob(os.path.join(saidas, "**", f"*.{extensao}"), recursive=True))
    for nome in ("index.html", "LEIA-ME.md", "README.md"):
        caminho = os.path.join(pasta, nome)
        if os.path.exists(caminho):
            achados.append(caminho)
    return achados


def registrar_projeto(pasta, tipo, pedido, resumo):
    with _trava:
        dados = _carregar()
        dados["projetos"] = [p for p in dados["projetos"] if p["pasta"] != pasta]
        dados["projetos"].append({
            "nome": os.path.basename(pasta), "pasta": pasta, "tipo": tipo, "pedido": pedido,
            "resumo": resumo, "arquivos": arquivos_gerados(pasta), "quando": _agora(),
        })
        _salvar(dados)


def projetos():
    """Projetos do mais novo para o mais antigo, com a lista de arquivos atualizada."""
    lista = list(reversed(_carregar()["projetos"]))
    for projeto in lista:
        if os.path.isdir(projeto["pasta"]):
            projeto["arquivos"] = arquivos_gerados(projeto["pasta"])
    return lista


def contexto():
    """Texto com o que o Jarvis lembra, para mandar junto com cada pedido ao Claude."""
    dados = _carregar()
    partes = []
    if dados["projetos"]:
        partes.append("Projetos que o Jarvis já criou (do mais recente para o mais antigo):")
        for projeto in projetos()[:PROJETOS_NO_CONTEXTO]:
            partes.append(f"- {projeto['nome']} ({projeto['tipo']}, {projeto['quando']}), pasta: {projeto['pasta']}")
            partes.append(f"  pedido: {projeto['pedido']}")
            if projeto.get("resumo"):
                partes.append(f"  resultado: {projeto['resumo']}")
            for caminho in projeto["arquivos"]:
                partes.append(f"  arquivo: {caminho}")
    falas = dados["conversa"][-FALAS_NO_CONTEXTO:]
    if falas:
        partes.append("")
        partes.append("Conversa recente entre o usuário e o Jarvis:")
        partes += [f"[{f['hora']}] {f['quem']}: {f['texto']}" for f in falas]
    return "\n".join(partes)
