"""WhatsApp Web na mini tela: o Braga manda UMA mensagem (e, se o usuário pedir, o vídeo) para UM contato da
última prospecção, sempre depois do "sim" do usuário.

A mensagem só pergunta se o comércio quer ver a prévia do site; quem disser que não, não recebe mais nada.
Não existe "mandar para todos": cada envio é um pedido e uma confirmação. Há um limite por dia (LIMITE_POR_DIA)
porque muitas mensagens para quem não tem você na agenda fazem o WhatsApp bloquear o número.

O login é o do próprio usuário: na primeira vez ele lê o QR Code do WhatsApp Web na mini tela com o celular;
o perfil do navegador guarda o login para as próximas vezes.
"""
import csv
import datetime
import glob
import json
import logging
import os
import re
import time
import unicodedata
import urllib.parse

import navegador
import prospeccao

PASTA = os.path.dirname(os.path.abspath(__file__))
REGISTRO = os.path.join(PASTA, "whatsapp_envios.json")
LIMITE_POR_DIA = 20
WHATSAPP = "https://web.whatsapp.com/"

log = logging.getLogger("jarvis")


def _normalizar(texto):
    texto = unicodedata.normalize("NFKD", (texto or "").lower())
    return re.sub(r"[^a-z0-9 ]+", " ", "".join(c for c in texto if not unicodedata.combining(c))).strip()


# ---------- contatos da última leva (prospecção ou fábrica de sites) ----------
def ultima_pasta_de_envio():
    """A pasta de envio mais recente (Vídeos\\Jarvis\\Prospecção\\... ou Vídeos\\Jarvis\\Sites\\...)."""
    raiz = os.path.join(prospeccao.pasta_videos(), "Jarvis")
    pastas = [os.path.dirname(c) for c in glob.glob(os.path.join(raiz, "*", "*", "contatos.csv"))]
    return max(pastas, key=os.path.getmtime) if pastas else None


def achar_em_todas(alvo):
    """Procura o contato na lista mais nova; pelo nome, também nas anteriores. Devolve (pasta, contato)."""
    raiz = os.path.join(prospeccao.pasta_videos(), "Jarvis")
    pastas = sorted((os.path.dirname(c) for c in glob.glob(os.path.join(raiz, "*", "*", "contatos.csv"))),
                    key=os.path.getmtime, reverse=True)
    if not pastas:
        return None, None
    contato = achar_contato(pastas[0], alvo)
    if contato or re.search(r"\d|proxim|primeir|segund|terceir", _normalizar(alvo)):
        return pastas[0], contato  # "próximo" e "contato 2" valem só para a lista mais nova
    for pasta in pastas[1:]:
        contato = achar_contato(pasta, alvo)
        if contato:
            return pasta, contato
    return pastas[0], None


def contatos(pasta):
    with open(os.path.join(pasta, "contatos.csv"), encoding="utf-8-sig", newline="") as arquivo:
        return list(csv.DictReader(arquivo, delimiter=";"))


def _salvar_contatos(pasta, lista):
    with open(os.path.join(pasta, "contatos.csv"), "w", encoding="utf-8-sig", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=list(lista[0].keys()), delimiter=";")
        escritor.writeheader()
        escritor.writerows(lista)


_NUMEROS = {"primeiro": 1, "segundo": 2, "terceiro": 3, "quarto": 4, "quinto": 5, "sexto": 6, "setimo": 7,
            "oitavo": 8, "nono": 9, "decimo": 10, "um": 1, "dois": 2, "tres": 3, "quatro": 4, "cinco": 5}


def achar_contato(pasta, alvo):
    """"próximo" (o primeiro ainda não enviado), "contato 2", "o segundo" ou parte do nome ("pet gato")."""
    lista = contatos(pasta)
    alvo_n = _normalizar(alvo)
    if not alvo_n or re.search(r"\bproxim\w*\b", alvo_n):
        return next((c for c in lista if c.get("whatsapp") and not c.get("enviado")), None)
    numero = re.search(r"\b(\d{1,2})\b", alvo_n) or re.search(r"\b(" + "|".join(_NUMEROS) + r")\b", alvo_n)
    if numero and re.fullmatch(r"(?:o |a |contato |numero |n )*\w+", alvo_n):
        n = int(numero.group(1)) if numero.group(1).isdigit() else _NUMEROS[numero.group(1)]
        return next((c for c in lista if str(c.get("numero")) == str(n)), None)
    palavras = [p for p in alvo_n.split() if p not in {"o", "a", "do", "da", "de", "pro", "pra", "para", "contato"}]
    # TODAS as palavras ditas precisam estar no nome: "pet gato" não pode cair no "Pet Shopping" por causa do "pet"
    achados = [c for c in lista if palavras and all(re.search(rf"\b{re.escape(p)}", _normalizar(c["nome"]))
                                                     for p in palavras)]
    return achados[0] if len(achados) == 1 else None


# ---------- limite por dia ----------
def _registro():
    try:
        with open(REGISTRO, encoding="utf-8") as arquivo:
            return json.load(arquivo)
    except (OSError, json.JSONDecodeError):
        return {"envios": []}


def enviados_hoje():
    hoje = datetime.date.today().isoformat()
    return sum(1 for e in _registro()["envios"] if e.get("quando", "").startswith(hoje))


def _anotar(contato, com_video):
    dados = _registro()
    dados["envios"].append({"quando": datetime.datetime.now().isoformat(timespec="seconds"),
                            "nome": contato["nome"], "whatsapp": contato["whatsapp"], "video": bool(com_video)})
    with open(REGISTRO, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=1)


# ---------- WhatsApp Web ----------
_JS_SITUACAO = r"""() => {
  if (document.querySelector('#pane-side, [aria-label="Lista de conversas"], [aria-label="Chat list"]')) return 'logado';
  if (document.querySelector('canvas[aria-label], [data-ref], [aria-label*="QR"], [aria-label*="Scan"]')) return 'qr';
  return 'carregando';
}"""


def situacao(espera=40):
    """Abre o WhatsApp Web na mini tela e diz se está "logado", pedindo o "qr" ou ainda "carregando"."""
    if WHATSAPP not in (navegador.estado().get("url") or ""):
        navegador.abrir(WHATSAPP)

    def olhar():
        pagina = navegador._pagina()
        fim = time.time() + espera
        estado = "carregando"
        while time.time() < fim:
            estado = pagina.evaluate(_JS_SITUACAO)
            if estado != "carregando":
                break
            pagina.wait_for_timeout(1500)
        return estado

    return navegador._rodar(olhar, limite=espera + 30)


def enviar(contato, texto, video=None):
    """Envia o texto (e o vídeo, se houver) para o contato pelo WhatsApp Web. Chamar só depois do "sim"."""
    if enviados_hoje() >= LIMITE_POR_DIA:
        raise RuntimeError(f"já foram {LIMITE_POR_DIA} mensagens hoje; o limite protege o seu número de bloqueio")
    numero = re.sub(r"\D", "", contato["whatsapp"])
    if not numero:
        raise ValueError("esse contato não tem celular")
    navegador.abrir(f"{WHATSAPP}send?phone={numero}&text={urllib.parse.quote(texto)}")

    def mandar():
        pagina = navegador._pagina()
        caixa = pagina.locator('footer [contenteditable="true"]').first
        try:
            caixa.wait_for(timeout=60000)
        except Exception:
            if pagina.locator('text=/inválido|invalid/i').count():
                raise ValueError("o WhatsApp diz que esse número não tem conta")
            raise RuntimeError("o WhatsApp Web não abriu a conversa (está logado? leia o QR Code na mini tela)")
        pagina.wait_for_timeout(1500)
        caixa.click()
        pagina.keyboard.press("Enter")  # o texto já veio escrito pelo link
        pagina.wait_for_timeout(2500)
        if video:
            botao = pagina.locator('[data-icon="plus-rounded"], [data-icon="plus"], [data-icon="attach-menu-plus"], '
                                   '[data-icon="clip"], [title="Anexar"], [aria-label="Anexar"]').first
            botao.click(timeout=15000)
            pagina.wait_for_timeout(1200)
            entrada = pagina.locator('input[type="file"][accept*="video"]').first
            entrada.set_input_files(video, timeout=15000)
            enviar_midia = pagina.locator('[data-icon="send"], [aria-label="Enviar"]').last
            enviar_midia.wait_for(timeout=60000)
            pagina.wait_for_timeout(1500)
            enviar_midia.click()
            pagina.wait_for_timeout(8000)  # dá tempo de o vídeo subir antes de sair da conversa
        return True

    navegador._rodar(mandar, limite=200)
    _anotar(contato, video)
    log.info("WhatsApp: enviado para %s%s", contato["nome"], " com vídeo" if video else "")


def marcar_enviado(pasta, contato, com_video):
    lista = contatos(pasta)
    for c in lista:
        if c["numero"] == contato["numero"]:
            c["enviado"] = f"{datetime.datetime.now():%d/%m %H:%M}" + (" (com vídeo)" if com_video else "")
    _salvar_contatos(pasta, lista)
