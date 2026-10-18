"""Envio de e-mail por voz. As credenciais ficam num arquivo que VOCÊ edita, nunca faladas em voz alta.

Para o Gmail: ative a verificação em duas etapas e crie uma "senha de app" em
https://myaccount.google.com/apppasswords. Use essa senha de 16 letras aqui, não a sua senha normal.
"""
import json
import logging
import os
import re
import smtplib
from email.message import EmailMessage

import segredos

PASTA = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(PASTA, "email_config.json")

MODELO = {
    "_ajuda": "Preencha com seu e-mail e a SENHA DE APP (não a senha normal). Gmail: servidor smtp.gmail.com, porta 587.",
    "remetente": "seu-email@gmail.com",
    "senha_de_app": "cole aqui a senha de app de 16 letras",
    "servidor": "smtp.gmail.com",
    "porta": 587,
    "contatos": {"exemplo": "pessoa@exemplo.com"},
}

log = logging.getLogger("jarvis")


def preparar():
    if not os.path.exists(CONFIG):
        with open(CONFIG, "w", encoding="utf-8") as arquivo:
            json.dump(MODELO, arquivo, ensure_ascii=False, indent=2)


def _config():
    """Lê a configuração primeiro do .env; o email_config.json fica como reserva (versão antiga)."""
    c = {}
    try:
        with open(CONFIG, encoding="utf-8") as arquivo:
            c = json.load(arquivo)
    except (OSError, json.JSONDecodeError):
        c = {}
    # O .env tem prioridade sobre o JSON
    email = segredos.obter("JARVIS_EMAIL")
    senha = segredos.obter("JARVIS_EMAIL_SENHA")
    if email and "seu-email" not in email:
        c["remetente"] = email
    if senha:
        c["senha_de_app"] = senha
    c["servidor"] = segredos.obter("JARVIS_SMTP", c.get("servidor", "smtp.gmail.com"))
    c["porta"] = segredos.obter("JARVIS_SMTP_PORTA", c.get("porta", 587))
    return c


def configurado():
    c = _config()
    senha = c.get("senha_de_app", "")
    return bool(c.get("remetente") and "@" in c.get("remetente", "")
                and senha and "cole aqui" not in senha)


def resolver_contato(nome):
    """Transforma um nome falado ('manda pro joão') num e-mail salvo nos contatos, se houver."""
    contatos = _config().get("contatos", {})
    alvo = nome.strip().lower()
    for apelido, email in contatos.items():
        if apelido.lower() == alvo or apelido.lower() in alvo or alvo in apelido.lower():
            return email
    return None


def interpretar(texto):
    """Extrai destinatário e mensagem de uma frase falada. Devolve (email, assunto, corpo) ou um erro em texto."""
    # e-mail dito por extenso: "fulano arroba gmail ponto com"
    t = texto
    t = re.sub(r"\s+arroba\s+", "@", t, flags=re.I)
    t = re.sub(r"\s+ponto\s+", ".", t, flags=re.I)
    achado = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", t)
    destino = achado.group() if achado else None

    corpo = texto
    m = re.search(r"\b(dizendo|falando|escreve[r]?|com a mensagem|que diz|avisa\w*|o seguinte)\b[:,]?\s*(.+)",
                  texto, flags=re.I)
    if m:
        corpo = m.group(2).strip()
    if destino:
        corpo = re.sub(re.escape(achado.group()), "", corpo).strip(" ,.:-")

    if not destino:
        alvo = re.search(r"\b(?:para|pro|pra|ao|a)\s+([a-zà-ú]+)", texto, flags=re.I)
        if alvo:
            destino = resolver_contato(alvo.group(1))
    if not destino:
        return None, None, None
    assunto = (corpo.split(".")[0][:60] or "Mensagem").strip()
    return destino, assunto, corpo


def enviar(destino, assunto, corpo):
    c = _config()
    msg = EmailMessage()
    msg["From"] = c["remetente"]
    msg["To"] = destino
    msg["Subject"] = assunto
    msg.set_content(corpo)
    with smtplib.SMTP(c.get("servidor", "smtp.gmail.com"), int(c.get("porta", 587)), timeout=30) as servidor:
        servidor.starttls()
        servidor.login(c["remetente"], c["senha_de_app"])
        servidor.send_message(msg)
    log.info("E-mail enviado para %s", destino)
