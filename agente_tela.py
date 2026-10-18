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

INSTRUCOES = (
    "Você é os olhos e as mãos do JARVIS, operando a tela do computador do usuário para cumprir uma tarefa. "
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


def executar_tarefa(tarefa, ao_evento=None):
    """Roda a tarefa no modo tela. Devolve (deu_certo, resumo)."""
    tela.preparar()
    historico = []
    for passo in range(1, MAX_PASSOS + 1):
        caminho, largura, altura = tela.capturar()
        pasta_foto = os.path.dirname(caminho)
        contexto = ""
        if historico:
            contexto = "Ações já feitas: " + "; ".join(historico[-6:]) + ".\n"
        pedido = (
            f"Tarefa do usuário: {tarefa}\n"
            f"{contexto}"
            f"A foto {os.path.basename(caminho)} tem {largura} por {altura} pixels. "
            f"Passo {passo} de no máximo {MAX_PASSOS}. Qual a próxima ação?"
        )
        deu_certo, resposta = claude_code.passo_visao(pedido, INSTRUCOES, pasta_foto)
        acao = _extrair_json(resposta or "")
        if not acao:
            log.warning("Modo tela: resposta sem JSON: %s", (resposta or "")[:200])
            return False, "Não consegui entender a tela, senhor."

        fala = acao.get("fala") or "Agindo na tela."
        if ao_evento:
            ao_evento(fala)
        log.info("Modo tela passo %d: %s | %s", passo, acao.get("acao"), fala)

        if acao.get("concluido") or acao.get("acao") == "concluir":
            return True, acao.get("resumo") or "Pronto, senhor."

        try:
            _fazer(acao)
        except Exception:
            log.exception("Falha ao executar a ação na tela")
            return False, "Tentei agir na tela mas algo deu errado, senhor."
        historico.append(f"{acao.get('acao')} {acao.get('texto') or acao.get('tecla') or ''}".strip())

    return True, "Cheguei ao limite de passos, senhor. Veja como ficou a tela."


def _fazer(acao):
    tipo = acao.get("acao")
    x, y = acao.get("x", 0), acao.get("y", 0)
    if tipo == "clicar":
        tela.clicar(x, y)
    elif tipo == "duplo":
        tela.clicar(x, y, duplo=True)
    elif tipo == "clique_direito":
        tela.clicar(x, y, botao="right")
    elif tipo == "digitar":
        tela.digitar(acao.get("texto", ""))
    elif tipo == "tecla":
        tela.tecla(acao.get("tecla", "enter"))
    elif tipo == "rolar":
        tela.rolar(acao.get("cliques", -3))
    elif tipo == "esperar":
        import time
        time.sleep(1.5)
