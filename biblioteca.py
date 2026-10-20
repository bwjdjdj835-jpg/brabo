"""Biblioteca do Jarvis: arquivos, fotos e links que você manda para ele estudar.

Cada item é copiado para biblioteca/arquivos, analisado pelo Claude e anotado em biblioteca/indice.json.
Quando o Claude cria ou altera um app, ele recebe esse índice e pode abrir os arquivos originais.
"""
import datetime
import json
import logging
import os
import queue
import re
import shutil
import threading
import unicodedata

PASTA = os.path.dirname(os.path.abspath(__file__))
BIBLIOTECA = os.path.join(PASTA, "biblioteca")
ARQUIVOS = os.path.join(BIBLIOTECA, "arquivos")
INDICE = os.path.join(BIBLIOTECA, "indice.json")
MEUS_DADOS = os.path.join(BIBLIOTECA, "meus_dados.md")
LIMITE_MB = 500  # APK comum tem poucos MB; APK grande de jogo pode passar de 100 MB
ITENS_NO_CONTEXTO = 30

IMAGENS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
DOCUMENTOS = {".pdf", ".txt", ".md", ".csv", ".json", ".html", ".css", ".js", ".ts", ".tsx", ".py", ".kt", ".xml"}
PACOTES = {".apk", ".aab", ".zip", ".jar"}

MODELO_MEUS_DADOS = """# Meus dados

Preencha do seu jeito. O Jarvis e o Claude usam estas informações em todos os apps e sites que criarem.

> NUNCA coloque aqui senhas, tokens ou chaves de API. Esses vão no arquivo .env.local de cada projeto.

## Negócio
- Nome da empresa / marca:
- O que eu vendo:
- Público-alvo:
- Preços e planos (ex.: mensal R$ 19,90, anual R$ 149,90):

## Identidade visual
- Cores (ex.: #0A84FF azul, #111111 fundo):
- Fontes:
- Estilo de interface que eu gosto:
- Logo: mande o arquivo para a biblioteca e escreva o nome aqui:

## Contato
- WhatsApp:
- E-mail:
- Instagram / site:

## Recebimentos
- Chave Pix (tipo e chave):
- Nome do recebedor:
- Provedor de pagamento que uso (Mercado Pago, Efí, Asaas...):

## Login nos apps
- Quero login com: (Google / e-mail e senha / telefone)
- Projeto do Firebase (nome ou ID, se já tiver):

## Observações
-
"""

INSTRUCOES = (
    "Você é o bibliotecário do BRAGA, o assistente do usuário. O usuário mandou um material para a biblioteca, "
    "que serve de referência quando o Claude criar apps e sites para ele. Abra o material indicado e responda "
    "SOMENTE com um resumo em português do Brasil, em texto simples, de no máximo 8 linhas: o que é e tudo o que "
    "for útil para criar apps (telas, layout, cores, fontes, textos, funcionalidades, regras de negócio, dados da "
    "empresa). Se for imagem de interface, descreva o layout e o estilo visual em detalhes. Se houver senhas ou "
    "chaves no material, não as repita e avise que elas não devem ficar na biblioteca. Termine com uma linha "
    "'Etiquetas:' e de 3 a 6 palavras-chave."
)

log = logging.getLogger("jarvis")
_trava = threading.Lock()
_fila = queue.Queue()
ao_concluir = None  # função(item) chamada quando uma análise termina


def preparar():
    os.makedirs(ARQUIVOS, exist_ok=True)
    if not os.path.exists(MEUS_DADOS):
        with open(MEUS_DADOS, "w", encoding="utf-8") as arquivo:
            arquivo.write(MODELO_MEUS_DADOS)
    threading.Thread(target=_trabalhar_fila, daemon=True).start()
    # retoma o que ficou pela metade da última vez
    for item in listar():
        if item["status"] == "analisando":
            _fila.put(item["id"])


def _agora():
    return datetime.datetime.now().strftime("%d/%m/%Y %H:%M")


def _carregar():
    try:
        with open(INDICE, encoding="utf-8") as arquivo:
            return json.load(arquivo)
    except (OSError, json.JSONDecodeError):
        return []


def _salvar(itens):
    temporario = INDICE + ".tmp"
    with open(temporario, "w", encoding="utf-8") as arquivo:
        json.dump(itens, arquivo, ensure_ascii=False, indent=1)
    os.replace(temporario, INDICE)


def _atualizar(id_item, **campos):
    with _trava:
        itens = _carregar()
        for item in itens:
            if item["id"] == id_item:
                item.update(campos)
                _salvar(itens)
                return item
    return None


def listar():
    """Itens do mais novo para o mais antigo."""
    return list(reversed(_carregar()))


def remover(ids):
    """Apaga itens do índice e os arquivos guardados. Quem chama deve ter pedido confirmação."""
    with _trava:
        itens = _carregar()
        alvos = [i for i in itens if i["id"] in ids]
        _salvar([i for i in itens if i["id"] not in ids])
    apagados = 0
    for item in alvos:
        arquivo = item.get("arquivo")
        if arquivo and os.path.exists(arquivo):
            try:
                os.remove(arquivo)
            except OSError:
                log.warning("Não consegui apagar %s", arquivo, exc_info=True)
                continue
        apagados += 1
    return apagados


def buscar(termo):
    """Itens cujo nome contém o termo falado."""
    termo = unicodedata.normalize("NFKD", termo.lower()).encode("ascii", "ignore").decode()
    achados = []
    for item in listar():
        nome = unicodedata.normalize("NFKD", item["nome"].lower()).encode("ascii", "ignore").decode()
        if termo and termo in nome:
            achados.append(item)
    return achados


def _nome_livre(nome):
    base, extensao = os.path.splitext(os.path.basename(nome))
    base = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode()
    base = re.sub(r"[^\w\-]+", "-", base).strip("-") or "arquivo"
    candidato, n = base + extensao.lower(), 2
    while os.path.exists(os.path.join(ARQUIVOS, candidato)):
        candidato, n = f"{base}-{n}{extensao.lower()}", n + 1
    return candidato


def _tipo(nome):
    extensao = os.path.splitext(nome)[1].lower()
    if extensao in IMAGENS:
        return "imagem"
    if extensao in DOCUMENTOS:
        return "documento"
    if extensao in PACOTES:
        return "pacote"
    return "arquivo"


def _novo_item(**campos):
    with _trava:
        itens = _carregar()
        item = {"id": f"{datetime.datetime.now():%Y%m%d%H%M%S%f}", "quando": _agora(),
                "status": "analisando", "resumo": "", **campos}
        itens.append(item)
        _salvar(itens)
    _fila.put(item["id"])
    log.info("Biblioteca recebeu %s: %s", item["tipo"], item["nome"])
    return item


def adicionar_arquivo(origem):
    if os.path.getsize(origem) > LIMITE_MB * 1024 * 1024:
        raise ValueError(f"O arquivo passa de {LIMITE_MB} MB.")
    destino = os.path.join(ARQUIVOS, _nome_livre(origem))
    shutil.copy2(origem, destino)
    return _novo_item(nome=os.path.basename(origem), tipo=_tipo(origem), arquivo=destino)


def adicionar_bytes(nome, dados):
    if len(dados) > LIMITE_MB * 1024 * 1024:
        raise ValueError(f"O arquivo passa de {LIMITE_MB} MB.")
    destino = os.path.join(ARQUIVOS, _nome_livre(nome))
    with open(destino, "wb") as arquivo:
        arquivo.write(dados)
    return _novo_item(nome=nome, tipo=_tipo(nome), arquivo=destino)


def adicionar_link(url):
    return _novo_item(nome=url, tipo="link", url=url)


def _trabalhar_fila():
    import claude_code  # aqui dentro para evitar importação circular

    while True:
        id_item = _fila.get()
        item = next((i for i in _carregar() if i["id"] == id_item), None)
        if not item:
            continue
        if item["tipo"] == "link":
            pedido = f"Analise este link: {item['url']}"
            ferramentas = ["WebFetch", "WebSearch"]
        elif item["nome"].lower().endswith((".apk", ".aab")):
            # APK é binário compactado: o Claude não consegue ler direto. O Jarvis extrai o manifesto
            # e a estrutura e manda esse texto (o Claude lê texto, não o arquivo).
            import engenharia
            try:
                relatorio = engenharia.relatorio_apk(item["arquivo"])
                pedido = ("Resuma para a biblioteca o que este APK é e como foi feito, a partir desta análise "
                          "estática. Não é preciso abrir nenhum arquivo.\n\n" + relatorio[:60000])
            except Exception as erro:
                log.exception("Falha ao ler o APK %s", item["nome"])
                pedido = f"Não consegui ler este APK ({erro}). Responda apenas: não foi possível analisar."
            ferramentas = ["Read"]
        else:
            pedido = f"Analise este arquivo: {item['arquivo']}"
            ferramentas = ["Read"]
        try:
            deu_certo, resposta = claude_code.analisar_material(pedido, INSTRUCOES, ferramentas)
        except Exception:
            log.exception("Falha ao analisar %s", item["nome"])
            deu_certo, resposta = False, ""
        item = _atualizar(id_item, status="pronto" if deu_certo else "erro",
                          resumo=resposta if deu_certo else "Não consegui analisar este item.")
        log.info("Biblioteca analisou %s: %s", item["nome"], "ok" if deu_certo else "erro")
        if ao_concluir:
            try:
                ao_concluir(item)
            except Exception:
                log.exception("Falha ao avisar sobre a biblioteca")


def contexto():
    """O que a biblioteca sabe, para mandar junto com os pedidos ao Claude."""
    partes = []
    try:
        with open(MEUS_DADOS, encoding="utf-8") as arquivo:
            dados = arquivo.read().strip()
        if dados and dados != MODELO_MEUS_DADOS.strip():
            partes += ["Dados do usuário (meus_dados.md):", dados]
    except OSError:
        pass
    itens = [i for i in listar() if i["status"] == "pronto"][:ITENS_NO_CONTEXTO]
    if itens:
        partes.append("")
        partes.append(f"Biblioteca de referências do usuário (arquivos em {ARQUIVOS}):")
        for item in itens:
            onde = item.get("url") or item.get("arquivo")
            partes.append(f"- {item['nome']} ({item['tipo']}, {item['quando']}): {onde}")
            partes.append("  " + item["resumo"].replace("\n", "\n  "))
    return "\n".join(partes)
