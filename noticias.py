"""Manchetes do Google Notícias (feed RSS, sem chave)."""
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

FEED = "https://news.google.com/rss?hl=pt-BR&gl=BR&ceid=BR:pt-419"
BUSCA = "https://news.google.com/rss/search?q={}&hl=pt-BR&gl=BR&ceid=BR:pt-419"


def manchetes(assunto="", quantidade=5):
    """Devolve [(título, fonte, link)] das notícias mais recentes, gerais ou de um assunto."""
    url = BUSCA.format(urllib.parse.quote_plus(assunto)) if assunto else FEED
    pedido = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(pedido, timeout=10) as resposta:
        raiz = ET.fromstring(resposta.read())
    lista = []
    for item in raiz.iter("item"):
        titulo = (item.findtext("title") or "").strip()
        fonte = (item.findtext("source") or "").strip()
        # o Google põe " - Fonte" no fim do título
        if fonte and titulo.endswith(" - " + fonte):
            titulo = titulo[: -len(fonte) - 3]
        if titulo:
            lista.append((titulo, fonte, (item.findtext("link") or "").strip()))
        if len(lista) >= quantidade:
            break
    return lista
