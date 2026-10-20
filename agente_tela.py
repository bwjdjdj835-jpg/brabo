"""Modo tela: o Jarvis vê a tela e age nela, passo a passo, até cumprir a tarefa.

A cada passo ele tira uma foto da tela, manda ao Claude, que decide a próxima ação (clicar, digitar,
rolar...), e o Jarvis executa. Repete até concluir ou atingir o limite de passos.

Segurança: o agente NÃO faz ações que não dá para desfazer nem que exigem segredo. Ele navega, pesquisa,
abre, rola e lê. Enviar, publicar, comprar, pagar, apagar e digitar senhas ficam com o usuário.
"""
import json
import logging
import os
import re

import claude_code
import tela

MAX_PASSOS = 10
MAX_PASSOS_NAVEGADOR = 15

INSTRUCOES = (
    "Você é os olhos e as mãos do BRAGA, operando a tela do computador do usuário para cumprir uma tarefa. "
    "A cada passo chega uma foto da tela (arquivo jarvis_tela.png nesta pasta) com a largura e a altura em pixels. "
    "Abra a foto com Read, veja o que está na tela e decida UMA ação. "
    "Responda SOMENTE com um JSON (sem texto antes ou depois) neste formato:\n"
    '{"fala": "frase curta em pt-BR do que você vai fazer", '
    '"acao": "clicar|duplo|clique_direito|digitar|tecla|rolar|esperar|concluir", '
    '"x": 0, "y": 0, "texto": "", "tecla": "enter", "cliques": -3, '
    '"concluido": false, "resumo": "quando concluir, diga em pt-BR o que fez ou o que viu"}\n'
    "Regras das coordenadas: x e y são o ponto a clicar, no mesmo espaço de pixels da foto informada. "
    "'rolar': cliques negativos descem, positivos sobem. 'tecla' aceita combinações como 'ctrl+a' ou 'enter'. "
    "'digitar' escreve no campo que já está focado (clique nele antes). 'esperar' quando a tela ainda carrega.\n"
    "SEGURANÇA, muito importante: você NÃO deve clicar em botões de enviar, publicar, postar, comprar, pagar, "
    "transferir, confirmar compra ou excluir, nem digitar senhas, números de cartão ou documentos. "
    "Se a tarefa chegar num desses pontos, pare com acao 'concluir', concluido true e um resumo dizendo que o "
    "usuário precisa terminar esse passo. Quando a tarefa for cumprida, use acao 'concluir' com um resumo útil."
)

INSTRUCOES_NAVEGADOR = INSTRUCOES.replace(
    "Abra a foto com Read, veja o que está na tela e decida UMA ação. ",
    "Decida UMA ação. Quase sempre a lista de elementos que vem no pedido basta, e decidir sem abrir a foto é "
    "bem mais rápido: só abra a foto com Read se a lista não deixar claro o que fazer (página em branco, lista "
    "vazia, imagem, captcha, ou para conferir o resultado). ") + (
    "\nVocê está operando a MINI TELA do Braga: um navegador Edge de 1280 por 800 pixels (a foto é a página "
    "inteira visível, sem barra de endereço). Há uma ação a mais: 'abrir', com o campo \"url\" (um endereço como "
    "https://... ou um texto para buscar no Bing, a busca da Microsoft). Use 'abrir' em vez de procurar uma "
    "barra de endereço. "
    "Junto com cada foto vêm o endereço e o título da página atual e a LISTA NUMERADA dos botões, links e campos "
    "visíveis, com o texto e o centro (x,y) de cada um. Para clicar ou preencher algo da lista, mande o número "
    "no campo \"id\" (ex.: {\"acao\": \"clicar\", \"id\": 12}) em vez de x e y: é muito mais certeiro. Use x e y só "
    "para o que não estiver na lista. Para escrever num campo, mande {\"acao\": \"digitar\", \"id\": N, "
    "\"texto\": \"...\", \"enter\": true}: o Jarvis clica no campo, escreve e aperta Enter se pedir. "
    "Se a página ainda está carregando, use 'esperar'. Não repita a mesma ação que não funcionou: tente outro "
    "caminho (outro elemento, rolar, ou 'abrir' com uma busca)."
)

log = logging.getLogger("jarvis")


def _extrair_json(texto):
    inicio = texto.find("{")
    fim = texto.rfind("}")
    if inicio < 0 or fim <= inicio:
        return None
    try:
        return json.loads(texto[inicio:fim + 1])
    except json.JSONDecodeError:
        return None


def executar_tarefa(tarefa, ao_evento=None, alvo=None):
    """Roda a tarefa no modo tela (alvo=tela, a tela inteira) ou na mini tela (alvo=navegador).
    Devolve (deu_certo, resumo)."""
    alvo = alvo or tela
    navegador = hasattr(alvo, "abrir")
    instrucoes = INSTRUCOES_NAVEGADOR if navegador else INSTRUCOES
    max_passos = MAX_PASSOS_NAVEGADOR if navegador else MAX_PASSOS
    alvo.preparar()
    historico = []
    for passo in range(1, max_passos + 1):
        caminho, largura, altura = alvo.capturar()
        pasta_foto = os.path.dirname(caminho)
        contexto = ""
        if historico:
            contexto = "Ações já feitas: " + "; ".join(historico[-6:]) + ".\n"
        itens = []
        if navegador:
            pagina = alvo.estado()
            contexto += f"Página atual: {pagina['titulo']} ({pagina['url']}).\n"
            try:
                itens = alvo.elementos()
            except Exception:
                log.warning("Mini tela: não consegui listar os elementos da página", exc_info=True)
            if itens:
                contexto += "Elementos visíveis (número: tipo 'texto' em x,y):\n" + "\n".join(
                    f"{e['id']}: {e['tipo']} '{e['texto']}' em {e['x']},{e['y']}" for e in itens) + "\n"
        pedido = (
            f"Tarefa do usuário: {tarefa}\n"
            f"{contexto}"
            f"A foto {os.path.basename(caminho)} tem {largura} por {altura} pixels. "
            f"Passo {passo} de no máximo {max_passos}. Qual a próxima ação?"
        )
        acao = None
        for _ in range(2):  # resposta cortada ou sem JSON: pergunta mais uma vez antes de desistir
            deu_certo, resposta = claude_code.passo_visao(pedido, instrucoes, pasta_foto)
            acao = _extrair_json(resposta or "")
            if acao:
                break
            log.warning("Modo tela: resposta sem JSON: %s", (resposta or "")[:200])
        if not acao:
            return False, "Não consegui entender a tela, senhor."
        if navegador and acao.get("id") is not None:
            elemento = next((e for e in itens if str(e["id"]) == str(acao["id"])), None)
            if elemento:
                acao["x"], acao["y"] = elemento["x"], elemento["y"]
                acao["_alvo"] = f"{elemento['tipo']} '{elemento['texto']}'"

        fala = acao.get("fala") or "Agindo na tela."
        if ao_evento:
            ao_evento(fala)
        log.info("Modo tela passo %d: %s | %s", passo, acao.get("acao"), fala)

        if acao.get("concluido") or acao.get("acao") == "concluir":
            return True, acao.get("resumo") or "Pronto, senhor."

        try:
            _fazer(acao, alvo)
        except Exception:
            log.exception("Falha ao executar a ação na tela")
            return False, "Tentei agir na tela mas algo deu errado, senhor."
        historico.append(" ".join(str(p) for p in (
            acao.get("acao"), acao.get("_alvo") or "", acao.get("texto") or acao.get("tecla") or acao.get("url") or "")
            if p).strip())
        if navegador:
            import time
            time.sleep(0.8)  # dá tempo de a página reagir antes da próxima foto

    return True, "Cheguei ao limite de passos, senhor. Veja como ficou a tela."


def _fazer(acao, alvo=tela):
    tipo = acao.get("acao")
    x, y = acao.get("x", 0), acao.get("y", 0)
    if tipo == "clicar":
        alvo.clicar(x, y)
    elif tipo == "duplo":
        alvo.clicar(x, y, duplo=True)
    elif tipo == "clique_direito":
        alvo.clicar(x, y, botao="right")
    elif tipo == "digitar":
        if acao.get("_alvo"):  # mini tela, campo da lista: clica nele antes de escrever
            alvo.clicar(x, y)
            alvo.tecla("ctrl+a")
        alvo.digitar(acao.get("texto", ""))
        if acao.get("enter"):
            alvo.tecla("enter")
    elif tipo == "tecla":
        alvo.tecla(acao.get("tecla", "enter"))
    elif tipo == "rolar":
        alvo.rolar(acao.get("cliques", -3))
    elif tipo == "abrir" and hasattr(alvo, "abrir"):
        alvo.abrir(acao.get("url") or acao.get("texto") or "")
    elif tipo == "esperar":
        import time
        time.sleep(1.5)
