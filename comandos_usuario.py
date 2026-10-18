"""Comandos criados por você, no arquivo meus_comandos.json.

Lê o arquivo a cada comando, então basta salvar para valer. Os tipos de ação são fixos e seguros:
não existe "executar comando de terminal" aqui; programas são abertos sem shell.
"""
import json
import logging
import os
import re
import subprocess
import unicodedata
import webbrowser

PASTA = os.path.dirname(os.path.abspath(__file__))
ARQUIVO = os.path.join(PASTA, "meus_comandos.json")

log = logging.getLogger("jarvis")


def _normalizar(texto):
    sem = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in sem if unicodedata.category(c) != "Mn")


def _carregar():
    try:
        with open(ARQUIVO, encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
        return [c for c in dados.get("comandos", []) if isinstance(c, dict)]
    except (OSError, json.JSONDecodeError):
        log.warning("meus_comandos.json inválido ou ausente", exc_info=True)
        return []


def _casa(frase, texto):
    """A frase do comando casa se todas as palavras dela aparecem no que foi falado."""
    palavras = re.findall(r"\w+", _normalizar(frase))
    return bool(palavras) and all(re.search(rf"\b{re.escape(p)}\b", texto) for p in palavras)


def tentar(texto_normalizado):
    """Se algum comando seu casar, devolve a resposta em texto. Senão, None."""
    for comando in _carregar():
        frases = comando.get("frases", [])
        if not any(_casa(f, texto_normalizado) for f in frases):
            continue
        acao = comando.get("acao", {})
        try:
            return _executar_acao(acao)
        except Exception:
            log.exception("Falha no comando do usuário %r", frases[:1])
            return "Não consegui executar esse comando, senhor. Veja o registro."
    return None


def _executar_acao(acao):
    tipo = acao.get("tipo")
    if tipo == "responder":
        return acao.get("texto", "Feito, senhor.")
    if tipo == "abrir":
        alvo = acao.get("alvo", "")
        if alvo.startswith(("http://", "https://")):
            webbrowser.open(alvo)
        else:
            os.startfile(alvo)
        return "Abrindo, senhor."
    if tipo == "pasta":
        os.startfile(acao.get("caminho", PASTA))
        return "Abrindo a pasta, senhor."
    if tipo == "programa":
        # sem shell: o caminho e os argumentos vão direto ao programa
        subprocess.Popen([acao.get("caminho")] + list(acao.get("args", [])),
                         creationflags=subprocess.CREATE_NO_WINDOW)
        return "Abrindo o programa, senhor."
    return f"Não conheço o tipo de ação '{tipo}' no seu arquivo, senhor."
