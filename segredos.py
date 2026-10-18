"""Lê os segredos do Jarvis de um arquivo .env, para não ficarem soltos no código nem na biblioteca.

O arquivo .env NUNCA deve ser compartilhado, colocado na biblioteca ou mostrado em prints.
É só um texto com linhas no formato CHAVE=valor. Linhas em branco e as que começam com # são ignoradas.
"""
import logging
import os
import shutil

PASTA = os.path.dirname(os.path.abspath(__file__))
ENV = os.path.join(PASTA, ".env")
EXEMPLO = os.path.join(PASTA, ".env.exemplo")

MODELO = """# Segredos do Jarvis. NÃO compartilhe este arquivo nem o coloque na biblioteca.
# Preencha o que for usar e salve. Linhas com # são comentários.

# --- E-mail (Gmail: crie uma "senha de app" em myaccount.google.com/apppasswords) ---
JARVIS_EMAIL=seu-email@gmail.com
JARVIS_EMAIL_SENHA=
JARVIS_SMTP=smtp.gmail.com
JARVIS_SMTP_PORTA=587

# --- Telegram (crie o bot no @BotFather e cole o token aqui) ---
JARVIS_TELEGRAM_TOKEN=
# Seu ID numérico do Telegram (descubra falando com @userinfobot). Vários separados por vírgula.
JARVIS_TELEGRAM_IDS=
"""

log = logging.getLogger("jarvis")
_cache = None


def preparar():
    """Cria o .env.exemplo e, se ainda não existir, o próprio .env a partir do modelo."""
    try:
        with open(EXEMPLO, "w", encoding="utf-8") as arquivo:
            arquivo.write(MODELO)
        if not os.path.exists(ENV):
            shutil.copy2(EXEMPLO, ENV)
    except OSError:
        log.warning("Não consegui preparar o .env", exc_info=True)


def _carregar():
    valores = {}
    try:
        with open(ENV, encoding="utf-8") as arquivo:
            for linha in arquivo:
                linha = linha.strip()
                if not linha or linha.startswith("#") or "=" not in linha:
                    continue
                chave, valor = linha.split("=", 1)
                valores[chave.strip()] = valor.strip().strip('"').strip("'")
    except OSError:
        pass
    return valores


def recarregar():
    global _cache
    _cache = _carregar()
    return _cache


def obter(chave, padrao=None):
    global _cache
    if _cache is None:
        _cache = _carregar()
    valor = _cache.get(chave)
    return valor if valor else padrao


def caminho():
    return ENV
