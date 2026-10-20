"""Relatório em PDF de uma playlist (ou de uma busca) do YouTube.

Para cada vídeo: título, canal, duração, data, visualizações, link e descrição. Os primeiros vídeos
(COM_LEGENDA) também têm as legendas lidas, e o Claude escreve um resumo geral, os pontos principais e um
resumo de cada vídeo. O PDF fica em pdfs/ e vai também para o Google Drive, se ele estiver instalado.
"""
import datetime
import json
import logging
import os
import re

import claude_code
import conversor_pdf
import google_drive
import youtube
from fpdf.enums import WrapMode, XPos, YPos

COM_LEGENDA = 10                 # quantos vídeos têm a fala lida (cada um é um pedido ao YouTube)
CARACTERES_POR_LEGENDA = 12_000
MAX_VIDEOS = 200

INSTRUCOES = (
    "Você é o analista do BRAGA. Vai receber os dados de vídeos de uma playlist ou busca do YouTube: título, "
    "canal, descrição e, em alguns, a legenda (o que é falado). Escreva em português do Brasil e responda "
    "SOMENTE com um JSON válido, sem texto antes ou depois, neste formato:\n"
    '{"falado": "uma ou duas frases curtas, sem markdown, para o Jarvis falar em voz alta", '
    '"resumo_geral": "um parágrafo de 4 a 8 frases sobre o conjunto: do que trata, para quem é, o que se aprende", '
    '"pontos_principais": ["5 a 10 pontos curtos com o mais importante"], '
    '"videos": {"1": "resumo do vídeo 1", "2": "..."}}\n'
    "Em 'videos', use o número de cada vídeo. Com legenda: 3 a 6 frases com o conteúdo de verdade (passos, "
    "ferramentas, dicas, conclusões). Sem legenda: uma frase a partir do título e da descrição. "
    "Não invente nada que não esteja nos dados."
)

log = logging.getLogger("jarvis")


def _duracao(segundos):
    segundos = int(segundos or 0)
    h, resto = divmod(segundos, 3600)
    m, s = divmod(resto, 60)
    return f"{h}h{m:02d}min" if h else f"{m}:{s:02d}"


def _numero(n):
    return f"{n:,}".replace(",", ".") if n is not None else "—"


def _json(texto):
    inicio, fim = texto.find("{"), texto.rfind("}")
    if inicio < 0 or fim < 0:
        return {}
    try:
        return json.loads(texto[inicio:fim + 1])
    except json.JSONDecodeError:
        log.warning("Resposta do Claude não era JSON: %s", texto[:300])
        return {}


def _analisar(titulo, videos):
    """Pede ao Claude o resumo geral e o de cada vídeo. Sem Claude, o relatório sai só com os dados."""
    if not claude_code.disponivel():
        return {}
    partes = []
    for n, video in enumerate(videos, 1):
        parte = (f"### Vídeo {n}: {video['titulo']}\nCanal: {video['canal']}\n"
                 f"Descrição: {video['descricao'][:800]}")
        if video["texto"]:
            parte += f"\nLegenda: {video['texto'][:CARACTERES_POR_LEGENDA]}"
        partes.append(parte)
    deu_certo, resposta = claude_code.resumir(f"Playlist/busca: {titulo}\n\n" + "\n\n".join(partes),
                                              INSTRUCOES, limite=900)
    return _json(resposta) if deu_certo else {}


def _pdf(titulo, origem, videos, analise):
    pdf = conversor_pdf._Pdf()
    pdf.set_title(titulo)
    pdf.set_creator("J.A.R.V.I.S.")
    pdf.add_page()

    def texto(tamanho, conteudo, estilo="", cor=0, altura=None, quebra=WrapMode.WORD):
        pdf.fonte("sans", estilo, tamanho)
        if isinstance(cor, tuple):
            pdf.set_text_color(*cor)
        else:
            pdf.set_text_color(cor)
        pdf.multi_cell(0, altura or tamanho * 0.5, pdf.limpar(conteudo), wrapmode=quebra,
                       new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(0)

    total = sum(v["duracao"] for v in videos)
    texto(9, "J.A.R.V.I.S. · RELATÓRIO DO YOUTUBE", "B", (0, 150, 190))
    texto(20, titulo, "B", altura=9)
    texto(9, f"{len(videos)} vídeos · {_duracao(total)} no total · gerado em "
             f"{datetime.datetime.now():%d/%m/%Y %H:%M}", cor=110)
    if youtube.eh_link(origem):
        pdf.fonte("sans", "", 9)
        pdf.set_text_color(0, 102, 204)
        pdf.cell(0, 5, origem[:110], link=origem, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(0)
    pdf.ln(4)

    if analise.get("resumo_geral"):
        pdf.start_section("Resumo geral")
        texto(13, "Resumo geral", "B", altura=7)
        texto(10.5, analise["resumo_geral"], altura=5.5)
        pdf.ln(3)
    if analise.get("pontos_principais"):
        pdf.start_section("Pontos principais")
        texto(13, "Pontos principais", "B", altura=7)
        for ponto in analise["pontos_principais"]:
            texto(10.5, f"•  {ponto}", altura=5.5)
        pdf.ln(3)

    # índice com links para cada vídeo dentro do PDF
    texto(13, "Vídeos", "B", altura=7)
    links = [pdf.add_link() for _ in videos]
    pdf.fonte("sans", "", 9.5)
    for n, (video, link) in enumerate(zip(videos, links), 1):
        nome = pdf.limpar(f"{n}. {video['titulo']}")
        while pdf.get_string_width(nome) > pdf.epw - 22 and len(nome) > 10:
            nome = nome[:-2]
        pdf.cell(pdf.epw - 20, 5.2, nome, link=link)
        pdf.cell(20, 5.2, _duracao(video["duracao"]), align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    resumos = analise.get("videos") or {}
    for n, (video, link) in enumerate(zip(videos, links), 1):
        if n == 1 or pdf.get_y() > pdf.h - 70:
            pdf.add_page()
        else:
            pdf.ln(4)
            pdf.set_draw_color(200)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
            pdf.ln(4)
        pdf.set_link(link, page=pdf.page, y=pdf.get_y())
        pdf.start_section(f"{n}. {video['titulo']}"[:120])
        texto(12.5, f"{n}. {video['titulo']}", "B", altura=6.2)
        detalhes = [video["canal"], _duracao(video["duracao"]), video["data"],
                    f"{_numero(video['visualizacoes'])} visualizações"]
        texto(9, " · ".join(d for d in detalhes if d), cor=110)
        pdf.fonte("sans", "", 9)
        pdf.set_text_color(0, 102, 204)
        pdf.cell(0, 5, video["url"][:100], link=video["url"], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(0)
        resumo = resumos.get(str(n)) or resumos.get(n)
        if resumo:
            pdf.ln(1.5)
            texto(10.5, resumo, altura=5.4)
        if video["descricao"].strip():
            pdf.ln(1.5)
            descricao = re.sub(r"\n{3,}", "\n\n", video["descricao"].strip())
            if len(descricao) > 900:
                descricao = descricao[:900].rsplit(" ", 1)[0] + "…"
            texto(8.5, "Descrição: " + descricao, cor=90, altura=4.3, quebra=WrapMode.CHAR)
    return pdf


def gerar(origem, quantidade=None, ao_evento=None):
    """Gera o relatório de uma playlist (link) ou busca (texto).

    Devolve {"pdf", "drive" (caminho no Drive ou None), "videos", "falado"}.
    """
    avisar = ao_evento or (lambda t: None)
    origem = origem.strip()
    avisar("Listando os vídeos")
    playlist = youtube.eh_playlist(origem)
    quantidade = max(1, min(quantidade or (MAX_VIDEOS if playlist else 20), MAX_VIDEOS))
    lista = youtube.listar(origem, quantidade, so_com_titulo=not youtube.eh_link(origem))[:quantidade]
    if not lista:
        raise ValueError(f"Não achei vídeos para '{origem}'.")
    titulo = youtube.nome_playlist(origem) if playlist else (lista[0]["titulo"] if youtube.eh_link(origem) else origem)

    videos = []
    for n, item in enumerate(lista, 1):
        avisar(f"Lendo {n}/{len(lista)} · {item['titulo'][:60]}")
        try:
            videos.append(youtube.detalhes(item["url"], legenda=n <= COM_LEGENDA))
        except Exception:
            log.warning("Falha ao ler %s", item["url"], exc_info=True)
            videos.append({"titulo": item["titulo"], "url": item["url"], "canal": "", "duracao": item["duracao"] or 0,
                           "data": "", "visualizacoes": None, "curtidas": None, "descricao": "", "texto": ""})

    avisar("O Claude está resumindo")
    analise = _analisar(titulo, videos)
    avisar("Montando o PDF")
    pdf = _pdf(titulo, origem, videos, analise)
    os.makedirs(conversor_pdf.SAIDA, exist_ok=True)
    caminho = os.path.join(conversor_pdf.SAIDA, conversor_pdf._nome_arquivo("relatorio " + titulo))
    pdf.output(caminho)
    drive = None
    try:
        drive = google_drive.salvar(caminho, os.path.join(google_drive.SUBPASTA, "Relatórios do YouTube"))
    except Exception:
        log.warning("Não consegui copiar o relatório para o Google Drive", exc_info=True)
    log.info("Relatório do YouTube: %s (%d vídeos)", caminho, len(videos))
    falado = analise.get("falado") or f"Relatório pronto, com {len(videos)} vídeos."
    return {"pdf": caminho, "drive": drive, "videos": len(videos), "falado": falado}
