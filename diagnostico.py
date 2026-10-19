"""Lê os erros recentes do registro (jarvis.log) para o Jarvis contar e, se o usuário quiser, mandar corrigir."""
import datetime
import os
import re

PASTA = os.path.dirname(os.path.abspath(__file__))
REGISTRO = os.path.join(PASTA, "jarvis.log")
BYTES_LIDOS = 400_000  # só o fim do registro, que pode ficar grande
LINHA = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d),\d+ (\w+) (.*)")


def ultimos_erros(quantidade=5, dias=7):
    """Erros (nível ERROR) dos últimos dias, do mais novo para o mais velho, sem repetir o mesmo erro.

    Cada um: {"quando": datetime, "mensagem", "excecao" (última linha do traceback), "trecho", "vezes"}.
    """
    try:
        with open(REGISTRO, "rb") as arquivo:
            arquivo.seek(max(0, os.path.getsize(REGISTRO) - BYTES_LIDOS))
            texto = arquivo.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    limite = datetime.datetime.now() - datetime.timedelta(days=dias)
    erros, atual = [], None
    for linha in texto.splitlines():
        achado = LINHA.match(linha)
        if achado:
            atual = None
            quando = datetime.datetime.strptime(achado.group(1), "%Y-%m-%d %H:%M:%S")
            if achado.group(2) == "ERROR" and quando >= limite:
                atual = {"quando": quando, "mensagem": achado.group(3).strip(), "linhas": []}
                erros.append(atual)
        elif atual is not None and linha.strip():
            atual["linhas"].append(linha.rstrip())

    unicos = {}
    for erro in reversed(erros):
        linhas = erro.pop("linhas")
        erro["excecao"] = linhas[-1].strip() if linhas else ""
        erro["trecho"] = "\n".join([erro["mensagem"]] + linhas[-12:])
        chave = (erro["mensagem"][:80], erro["excecao"][:120])
        if chave in unicos:
            unicos[chave]["vezes"] += 1
        else:
            erro["vezes"] = 1
            unicos[chave] = erro
    return list(unicos.values())[:quantidade]
