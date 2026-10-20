"""Fábrica de sites (código B/07070707): negócios SEM site no Google Maps -> print -> domínio livre ->
modelo de design -> site pronto -> zip -> vídeo da prévia -> mensagem para o cliente -> (com confirmação) site
publicado no GitHub Pages.

Cuidados:
- Fotos do Google Maps são de quem as tirou: o site não usa essas fotos. Elas aparecem só no print, que serve de
  referência; o cliente manda as próprias fotos depois.
- O site leva uma faixa "prévia de demonstração" e não aparece no Google (noindex) até o cliente aprovar.
- Publicar no GitHub deixa o site público: o Jarvis só publica depois do "sim" do usuário (ver github_pages.py).
- As mensagens não são enviadas pelo Jarvis: ficam prontas na página de entregas, para o usuário enviar uma a uma.

Tudo fica em sites_clientes/<data-busca>/: entregas.html, sites.json, <comércio>/site/, <comércio>/prints/,
<comércio>.zip. Os vídeos MP4 vão para Vídeos\\Jarvis\\Sites\\<data-busca>\\.
"""
import datetime
import hashlib
import html
import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import zipfile

import navegador
import prospeccao

PASTA = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(PASTA, "sites_clientes")
VIDEOS = os.path.join(prospeccao.pasta_videos(), "Jarvis", "Sites")
PADRAO = 3
MAXIMO = 8
REDES = ("instagram.com", "facebook.com", "wa.me", "whatsapp.com", "linktr.ee", "tiktok.com")

log = logging.getLogger("jarvis")
_slug = prospeccao._slug


# ---------- 1. negócios sem site ----------
def sem_site(negocio):
    """Sem site de verdade: nenhum endereço, ou só rede social / link do WhatsApp."""
    site = (negocio.get("site") or "").lower()
    return not site or any(rede in site for rede in REDES)


def buscar_sem_site(busca, quantidade, avisar):
    candidatos = prospeccao.buscar_negocios(busca, min(quantidade * 3, prospeccao.MAX_NEGOCIOS), avisar)
    escolhidos = [n for n in candidatos if sem_site(n)][:quantidade]
    log.info("Fábrica de sites: %d de %d negócios de '%s' estão sem site", len(escolhidos), len(candidatos), busca)
    return escolhidos


# ---------- 2. print do Google Maps ----------
def print_do_maps(negocio, destino):
    """Foto da página do negócio no Google Maps (nome, nota, fotos, horários), para referência."""
    navegador.abrir(negocio["link_maps"])

    def foto():
        pagina = navegador._pagina()
        try:
            pagina.wait_for_selector("h1", timeout=20000)
            pagina.wait_for_timeout(2500)
        except Exception:
            pass
        return navegador._foto(pagina, "png")

    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with open(destino, "wb") as arquivo:
        arquivo.write(navegador._rodar(foto, limite=60))
    return destino


# Fotos que aparecem na página do negócio no Maps (a de capa e as da galeria). O endereço sem o "=w..." no fim é a
# foto em si; pedimos a versão grande.
_JS_FOTOS = r"""() => {
  const vistos = new Set(), saida = [];
  for (const img of document.querySelectorAll('img')) {
    const src = img.currentSrc || img.src || '';
    // grass-cs é o endereço atual das fotos dos lugares; /a/ e /a- são fotos de perfil de quem avaliou (fora)
    if (!/googleusercontent\.com\/(p\/|gps-cs|gps-proxy|geougc|grass-cs)/.test(src)) continue;
    const base = src.split('=')[0];
    if (vistos.has(base)) continue;
    vistos.add(base);
    saida.push(base);
  }
  return saida.slice(0, 12);
}"""


def baixar_fotos(pasta_fotos, maximo=6):
    """Baixa as fotos do negócio que estão na página aberta do Maps (chamar logo depois do print).

    As fotos do Maps são de quem as tirou (o dono ou clientes): servem para a prévia que vai ser mostrada ao
    próprio dono, e ele precisa autorizar antes de o site virar oficial."""
    def achar():
        pagina = navegador._pagina()
        enderecos = pagina.evaluate(_JS_FOTOS)  # as da página do lugar (capa e algumas da galeria)
        try:  # abre a galeria (clicando na foto de capa) para carregar mais fotos
            capa = pagina.locator('button[aria-label^="Foto de"], button[jsaction*="heroHeaderImage"]').first
            capa.click(timeout=5000)
            pagina.wait_for_timeout(2500)
            pagina.mouse.move(300, 450)
            for _ in range(3):
                pagina.mouse.wheel(0, 1200)
                pagina.wait_for_timeout(800)
            enderecos += [e for e in pagina.evaluate(_JS_FOTOS) if e not in enderecos]
        except Exception:
            log.info("Fábrica de sites: não deu para abrir a galeria de fotos do Maps", exc_info=True)
        return enderecos

    enderecos = navegador._rodar(achar, limite=40)
    os.makedirs(pasta_fotos, exist_ok=True)
    salvas, vistas = [], set()
    for base in enderecos:
        if len(salvas) >= maximo:
            break
        try:
            pedido = urllib.request.Request(base + "=w1600-h1000-k-no", headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(pedido, timeout=20) as resposta:
                dados = resposta.read()
        except (urllib.error.URLError, OSError):
            continue
        if len(dados) < 12_000:  # ícone ou miniatura, não foto
            continue
        impressao = hashlib.md5(dados).hexdigest()
        if impressao in vistas:  # a mesma foto com outro endereço
            continue
        vistas.add(impressao)
        caminho = os.path.join(pasta_fotos, f"foto-{len(salvas) + 1}.jpg")
        with open(caminho, "wb") as arquivo:
            arquivo.write(dados)
        salvas.append(caminho)
    log.info("Fábrica de sites: %d fotos baixadas em %s", len(salvas), pasta_fotos)
    return salvas


# ---------- 3. domínio ----------
def _rdap(url):
    """True = registrado, False = livre, None = não deu para saber."""
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Jarvis"}), timeout=12):
            return True
    except urllib.error.HTTPError as erro:
        return False if erro.code == 404 else None
    except (urllib.error.URLError, OSError):
        return None


GENERICAS = {"barbearia", "barbershop", "barber", "salao", "loja", "restaurante", "lanchonete", "pizzaria", "clinica",
             "oficina", "studio", "estudio", "em", "de", "da", "do", "das", "dos", "e", "a", "o", "unidade", "filial",
             "ltda", "me", "eireli", "cia", "centro"}


def _marca(nome, cidade=""):
    """A parte do nome que é a marca: "Barbearia em Cacoal - Forbici Barbearia Unidade 2" -> "forbici"."""
    partes = re.split(r"\s+[-|–]\s+|\s*\|\s*", nome)
    # nomes "de SEO" do Maps ("Barbearia em Cacoal - Marca") têm a cidade numa parte e a marca em outra
    partes = [p for p in partes if not re.search(r"\bem\b", p, re.I)] or partes
    cidade_slug = set(_slug(cidade).split("-")) if cidade.strip() else set()
    palavras = [p for p in _slug(partes[0]).split("-") if p not in GENERICAS and p not in cidade_slug and not p.isdigit()]
    if len("".join(palavras[:3])) < 5:  # marca curta demais ("deck", "ze"): usa o nome inteiro, sem os conectivos
        palavras = [p for p in _slug(partes[0]).split("-")
                    if p not in {"em", "de", "da", "do", "das", "dos", "e", "a", "o", "ltda", "me", "eireli"}
                    and not p.isdigit()]
    return "".join(palavras[:3])[:30] or _slug(nome).replace("-", "")[:30]


def verificar_dominios(nome, cidade=""):
    """Sugere domínios para o negócio e confere na internet (RDAP do Registro.br e da Verisign) se estão livres."""
    base = _marca(nome, cidade)
    cidade = _slug(cidade).replace("-", "") if cidade.strip() else ""
    opcoes = [f"{base}.com.br", f"{base}{cidade}.com.br" if cidade else None, f"{base}.com"]
    resultado = []
    for dominio in [d for d in opcoes if d]:
        if dominio.endswith(".com.br"):
            registrado = _rdap(f"https://rdap.registro.br/domain/{dominio}")
        else:
            registrado = _rdap(f"https://rdap.verisign.com/com/v1/domain/{dominio}")
        resultado.append({"dominio": dominio,
                          "situacao": {True: "registrado", False: "livre", None: "não confirmado"}[registrado]})
    return resultado


# ---------- 3b. confirmar na web que não tem site (código C/19708090) ----------
# sites que aparecem na busca mas não são "o site do comércio": guias, redes, marketplaces, mapas, cadastros
NAO_E_SITE_PROPRIO = REDES + (
    "google.", "bing.", "microsoft.", "maps.", "ifood.", "rappi.", "aiqfome.", "apontador.", "guiamais.", "telelistas.",
    "cylex", "solutudo.", "encontra", "yelp.", "tripadvisor.", "foursquare.", "waze.", "youtube.", "kwai.", "threads.",
    "cnpj", "econodata.", "casadosdados.", "empresaqui.", "consultas", "jusbrasil.", "reclameaqui.", "olx.",
    "mercadolivre.", "shopee.", "doctoralia.", "booksy.", "trinks.", "petlove.", "gov.br", "wikipedia.", "x.com",
    "twitter.com", "linkedin.com", "pinterest.", "glassdoor.", "indeed.", "infojobs.", "vagas.", "listamais.",
)
_JS_LINKS_BING = r"""() => [...document.querySelectorAll('#b_results li.b_algo h2 a, #b_results li.b_algo .b_attribution cite')]
  .map(a => a.href || a.textContent).filter(Boolean).slice(0, 15)"""


def _links_da_busca(texto):
    navegador.abrir(texto, "bing")
    return navegador._rodar(lambda: navegador._pagina().evaluate(_JS_LINKS_BING), limite=30) or []


def _site_proprio(links, marca):
    """O primeiro link que parece ser o site do próprio comércio (o domínio tem a marca)."""
    for link in links:
        dominio = urllib.parse.urlsplit(link if "://" in link else "https://" + link.split(" ")[0]).netloc.lower()
        if not dominio or any(n in dominio for n in NAO_E_SITE_PROPRIO):
            continue
        if marca and len(marca) >= 4 and marca[:12] in dominio.replace("-", "").replace(".", ""):
            return dominio
    return None


def confirmar_sem_site(negocio, cidade, avisar):
    """Pesquisa no navegador (Bing) pelo nome e pelo telefone e confere os domínios parecidos. Devolve
    (True, motivo) se realmente não tem site, ou (False, "tem site: dominio")."""
    nome = negocio["nome"]
    marca = _marca(nome, cidade)
    buscas = [f'"{nome}" {cidade}'.strip()]
    telefone = re.sub(r"\D", "", negocio.get("telefone") or "")
    if len(telefone) >= 8:
        buscas.append(f'"{negocio["telefone"]}"')
    for busca in buscas:
        avisar(f"conferindo na web se {nome[:30]} tem site · {busca[:40]}")
        try:
            achado = _site_proprio(_links_da_busca(busca), marca)
        except Exception:
            log.warning("Fábrica de sites: busca de confirmação falhou (%s)", busca, exc_info=True)
            continue
        if achado:
            return False, f"tem site: {achado}"
    # domínio da marca registrado E respondendo com o nome do comércio = tem site, mesmo sem aparecer na busca
    for dominio in (f"{marca}.com.br", f"{marca}.com"):
        try:
            pedido = urllib.request.Request(f"https://{dominio}", headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(pedido, timeout=8) as resposta:
                pagina = resposta.read(200_000).decode("utf-8", "replace").lower()
        except (urllib.error.URLError, OSError, ValueError):
            continue
        palavras = [p for p in _slug(nome).split("-") if len(p) > 3 and p not in GENERICAS]
        if palavras and sum(p in pagina for p in palavras) >= max(1, len(palavras) // 2):
            return False, f"tem site: {dominio}"
    return True, "nenhum site próprio na busca pelo nome e pelo telefone"


# ---------- 4. modelos de design ----------
MODELOS = {
    "noturno": {"descricao": "escuro e elegante, com destaque em neon", "fundo": "#0b0f17", "texto": "#f1f5f9",
                "cartao": "rgba(255,255,255,.05)", "destaque": "#22d3ee", "fonte": "'Segoe UI', system-ui, sans-serif",
                "titulo": "'Segoe UI Black', 'Segoe UI', sans-serif"},
    "claro": {"descricao": "claro e sofisticado, com tons suaves", "fundo": "#faf7f2", "texto": "#1f2937",
              "cartao": "#ffffff", "destaque": "#b45309", "fonte": "Georgia, 'Times New Roman', serif",
              "titulo": "Georgia, serif"},
    "vibrante": {"descricao": "colorido e alegre, chamativo no celular", "fundo": "#fff7ed", "texto": "#1c1917",
                 "cartao": "#ffffff", "destaque": "#ea580c", "fonte": "'Segoe UI', system-ui, sans-serif",
                 "titulo": "'Segoe UI Black', 'Segoe UI', sans-serif"},
    "saude": {"descricao": "limpo e confiável, em azul e verde", "fundo": "#f0f9ff", "texto": "#0f172a",
              "cartao": "#ffffff", "destaque": "#0284c7", "fonte": "'Segoe UI', system-ui, sans-serif",
              "titulo": "'Segoe UI Semibold', 'Segoe UI', sans-serif"},
}
RAMOS_DOS_MODELOS = {
    "noturno": ("barbearia", "barber", "tatuagem", "tattoo", "academia", "oficina", "auto", "bar", "games"),
    "claro": ("salao", "beleza", "estetica", "manicure", "advoc", "contab", "imobili", "arquitet", "fotograf"),
    "vibrante": ("restaurante", "pizzaria", "lanchonete", "hamburg", "acai", "sorvet", "doceria", "padaria",
                 "pet", "loja", "festa", "buffet"),
    "saude": ("clinica", "dentista", "odonto", "fisio", "psicolog", "medic", "farmacia", "laborat", "nutri"),
}


# skins novos por ramo (código C/19708090): paleta + par de fontes do Google Fonts + formas, variando por comércio
PALETAS_POR_RAMO = {
    ("pet", "veterin", "banho", "tosa"): [("#fff8f0", "#2b2118", "#ff8a3d", "#2fb7a3"), ("#f4fbff", "#13293d", "#3a86ff", "#ffbe0b"),
                                          ("#fdf6ff", "#2d1b3d", "#9b5de5", "#f15bb5")],
    ("barbe", "barber", "tattoo", "tatu"): [("#0e0e10", "#f2efe9", "#c8a165", "#8b1e1e"), ("#111827", "#f9fafb", "#e11d48", "#fbbf24")],
    ("salao", "beleza", "estetica", "manicure", "spa"): [("#fff7f8", "#3a2730", "#d4789a", "#c9a96e"), ("#faf5ff", "#2e1065", "#a855f7", "#f9a8d4")],
    ("restaur", "pizza", "lanch", "hamburg", "acai", "sorvet", "doce", "padaria", "cafe"): [
        ("#fffaf0", "#2a1a0e", "#e63946", "#f4a261"), ("#101418", "#fdf6e3", "#ff7b00", "#ffd166")],
    ("clinica", "odonto", "dentista", "fisio", "psicolog", "medic", "farmacia", "nutri", "laborat"): [
        ("#f6fbff", "#0b2540", "#0ea5e9", "#10b981"), ("#ffffff", "#1e293b", "#2563eb", "#14b8a6")],
    ("academia", "fitness", "crossfit", "oficina", "auto", "moto", "pneu"): [("#0b0b0f", "#f5f5f5", "#a3e635", "#22d3ee"),
                                                                           ("#111111", "#fafafa", "#f97316", "#facc15")],
}
FONTES = [("Poppins", "Inter"), ("Playfair Display", "Lato"), ("Montserrat", "Open Sans"), ("Nunito", "Nunito Sans"),
          ("Bebas Neue", "Roboto"), ("Fredoka", "Quicksand"), ("DM Serif Display", "DM Sans"), ("Outfit", "Manrope")]
FORMAS = ["cantos bem arredondados e ícones fofos", "linhas retas e elegantes, muito espaço em branco",
          "ondas e curvas orgânicas nas divisórias", "cartões com sombra suave e destaques em gradiente",
          "visual de revista, fotos grandes e títulos enormes"]


def skin_novo(ramo, semente):
    """Um skin profissional próprio para o ramo, diferente de comércio para comércio (semente = nome)."""
    sorteio = hashlib.sha256(semente.encode("utf-8")).digest()  # um byte para cada escolha
    texto = _slug(ramo)
    paletas = next((p for chaves, p in PALETAS_POR_RAMO.items() if any(c in texto for c in chaves)),
                   [("#f8fafc", "#0f172a", "#6366f1", "#f59e0b"), ("#0f172a", "#e2e8f0", "#38bdf8", "#f472b6")])
    fundo, cor_texto, destaque, apoio = paletas[sorteio[0] % len(paletas)]
    titulo, corpo = FONTES[sorteio[1] % len(FONTES)]
    forma = FORMAS[sorteio[2] % len(FORMAS)]
    return {"fundo": fundo, "texto": cor_texto, "destaque": destaque, "apoio": apoio, "fonte_titulo": titulo,
            "fonte_texto": corpo, "forma": forma,
            "descricao": (f"SKIN NOVO e exclusivo para {ramo}: fundo {fundo}, texto {cor_texto}, destaque {destaque}, "
                          f"cor de apoio {apoio}; títulos em {titulo} e textos em {corpo} (Google Fonts); {forma}. "
                          "Crie elementos visuais que lembrem o ramo (ícones, ilustrações em SVG, detalhes) e não "
                          "copie o visual de outros sites")}


def escolher_modelo(ramo):
    texto = _slug(ramo)
    for modelo, palavras in RAMOS_DOS_MODELOS.items():
        if any(p in texto for p in palavras):
            return modelo
    return "noturno"


# ---------- 5. o site ----------
def construir_site(negocio, busca, pasta_site, modelo, skin=None):
    e = html.escape
    m = dict(MODELOS[modelo])
    fontes_google = ""
    if skin:  # o skin novo do ramo manda nas cores e nas fontes
        escuro = sum(int(skin["fundo"][i:i + 2], 16) for i in (1, 3, 5)) < 384
        m.update(fundo=skin["fundo"], texto=skin["texto"], destaque=skin["destaque"],
                 cartao="rgba(255,255,255,.06)" if escuro else "#ffffff",
                 fonte=f"'{skin['fonte_texto']}', 'Segoe UI', sans-serif", titulo=f"'{skin['fonte_titulo']}', 'Segoe UI', sans-serif")
        familias = "&".join("family=" + urllib.parse.quote_plus(f) + ":wght@400;700;800"
                            for f in {skin["fonte_titulo"], skin["fonte_texto"]})
        fontes_google = f'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?{familias}&display=swap">'
    nome = negocio["nome"]
    ramo = negocio.get("categoria") or busca
    achado = re.search(r",\s*([^,]+?)\s*-\s*[A-Z]{2}\b", negocio.get("endereco") or "")
    cidade = achado.group(1).strip() if achado else ""
    zap = prospeccao.whatsapp_de(negocio.get("telefone"))
    contato = f"https://wa.me/{zap}" if zap else (negocio.get("link_maps") or "#")
    iniciais = "".join(p[0] for p in re.findall(r"\w+", nome)[:2]).upper() or "★"
    servicos = "".join(f"<div class='cartao'><b>{i:02d}</b><h3>{e(s)}</h3><p>Fale com a gente e agende o seu horário."
                       f"</p></div>" for i, s in enumerate(prospeccao._servicos(f"{ramo} {busca}"), 1))
    nota = negocio.get("nota") or ""
    prova = (f"<section class='prova'><div class='numero'>★ {e(nota)}</div><p>nota no Google, com "
             f"{e(negocio.get('avaliacoes') or 'várias')} avaliações de clientes</p></section>") if nota else ""
    mapa = "https://www.google.com/maps?output=embed&q=" + urllib.parse.quote(f"{nome} {negocio.get('endereco', '')}")
    pagina = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>{e(nome)}{(' · ' + e(cidade)) if cidade else ''}</title>
<meta name="description" content="{e(nome)}: {e(ramo)}{(' em ' + e(cidade)) if cidade else ''}. Fale pelo WhatsApp.">
<meta property="og:title" content="{e(nome)}"><meta property="og:description" content="{e(ramo)}{(' em ' + e(cidade)) if cidade else ''}">
{fontes_google}
<style>
  :root {{ --fundo: {m['fundo']}; --texto: {m['texto']}; --cartao: {m['cartao']}; --destaque: {m['destaque']}; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html {{ scroll-behavior: smooth; }}
  body {{ font-family: {m['fonte']}; background: var(--fundo); color: var(--texto); line-height: 1.6; }}
  .faixa {{ background: var(--destaque); color: #fff; text-align: center; font: 600 13px/1.4 'Segoe UI', sans-serif; padding: 6px 12px; }}
  header {{ position: sticky; top: 0; z-index: 5; display: flex; align-items: center; justify-content: space-between;
           padding: 16px 6vw; background: color-mix(in srgb, var(--fundo) 88%, transparent); backdrop-filter: blur(8px); }}
  .marca {{ display: flex; gap: 12px; align-items: center; font: 700 19px {m['titulo']}; }}
  .logo {{ width: 44px; height: 44px; border-radius: 12px; display: grid; place-items: center; background: var(--destaque); color: #fff; }}
  nav a {{ color: inherit; text-decoration: none; margin-left: 22px; opacity: .8; font-size: 15px; }}
  .botao {{ display: inline-block; padding: 15px 28px; border-radius: 999px; background: var(--destaque); color: #fff;
            font-weight: 700; text-decoration: none; box-shadow: 0 12px 30px color-mix(in srgb, var(--destaque) 35%, transparent); }}
  .hero {{ min-height: 78vh; display: grid; align-content: center; padding: 60px 6vw;
           background: radial-gradient(circle at 85% 15%, color-mix(in srgb, var(--destaque) 28%, transparent), transparent 55%); }}
  .hero small {{ color: var(--destaque); font-weight: 700; letter-spacing: .14em; text-transform: uppercase; }}
  .hero h1 {{ font: 800 clamp(40px, 7vw, 84px)/1.02 {m['titulo']}; margin: 16px 0 20px; max-width: 920px; }}
  .hero p {{ font-size: 20px; opacity: .8; max-width: 620px; margin-bottom: 34px; }}
  section {{ padding: 80px 6vw; }}
  h2 {{ font: 700 clamp(28px, 4vw, 40px) {m['titulo']}; margin-bottom: 28px; }}
  .grade {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 18px; }}
  .cartao {{ background: var(--cartao); border-radius: 22px; padding: 28px; border: 1px solid color-mix(in srgb, var(--texto) 10%, transparent); }}
  .cartao b {{ color: var(--destaque); font-size: 14px; }} .cartao h3 {{ margin: 8px 0 6px; font-size: 20px; }}
  .cartao p {{ opacity: .7; font-size: 15px; }}
  .prova {{ text-align: center; }} .numero {{ font: 800 64px {m['titulo']}; color: var(--destaque); }}
  .local {{ display: grid; grid-template-columns: 1fr 1.3fr; gap: 32px; align-items: center; }}
  .local iframe {{ width: 100%; height: 340px; border: 0; border-radius: 22px; }}
  .chamada {{ text-align: center; background: var(--destaque); color: #fff; border-radius: 28px; margin: 0 6vw 80px; padding: 60px 6vw; }}
  .chamada .botao {{ background: #fff; color: var(--destaque); }}
  .flutuante {{ position: fixed; right: 18px; bottom: 18px; width: 58px; height: 58px; border-radius: 50%; background: #25d366;
                display: grid; place-items: center; color: #fff; font-size: 28px; text-decoration: none; box-shadow: 0 10px 25px rgba(0,0,0,.25); }}
  footer {{ padding: 30px 6vw 50px; text-align: center; opacity: .6; font-size: 14px; }}
  @media (max-width: 760px) {{ nav {{ display: none; }} .local {{ grid-template-columns: 1fr; }} }}
</style></head>
<body>
<div class="faixa">Prévia de demonstração · site não oficial de {e(nome)}</div>
<header><div class="marca"><div class="logo">{e(iniciais)}</div>{e(nome)}</div>
  <nav><a href="#servicos">Serviços</a><a href="#onde">Onde estamos</a><a href="{e(contato)}">Contato</a></nav></header>
<div class="hero">
  <small>{e(ramo)}{(' · ' + e(cidade)) if cidade else ''}</small>
  <h1>{e(nome)}</h1>
  <p>Atendimento caprichado, perto de você. Chame no WhatsApp e garanta o seu horário.</p>
  <div><a class="botao" href="{e(contato)}">Chamar no WhatsApp</a></div>
</div>
<section id="servicos"><h2>O que fazemos</h2><div class="grade">{servicos}</div></section>
{prova}
<section id="onde"><div class="local"><div><h2>Onde estamos</h2><p>{e(negocio.get('endereco') or 'Fale com a gente para saber o endereço.')}</p>
  <p style="margin-top:10px">{e(negocio.get('telefone') or '')}</p></div><iframe loading="lazy" src="{e(mapa)}"></iframe></div></section>
<div class="chamada"><h2>Bora marcar?</h2><p style="margin-bottom:26px">Responda rapidinho pelo WhatsApp.</p>
  <a class="botao" href="{e(contato)}">Falar agora</a></div>
<a class="flutuante" href="{e(contato)}" aria-label="WhatsApp">✆</a>
<footer>{e(nome)} · {e(negocio.get('endereco') or '')}</footer>
</body></html>"""
    os.makedirs(pasta_site, exist_ok=True)
    caminho = os.path.join(pasta_site, "index.html")
    with open(caminho, "w", encoding="utf-8") as arquivo:
        arquivo.write(pagina)
    return caminho


# ---------- 5b. o site grande, feito pelo Claude, em loop até passar na checagem ----------
INSTRUCOES_SITE = (
    "Você é o web designer do BRAGA. Nesta pasta há o arquivo dados.json (dados reais de um negócio, tirados do "
    "Google Maps) e a pasta fotos/ (fotos reais do negócio). Construa aqui o SITE COMPLETO, bonito e interativo "
    "desse negócio, pronto para mostrar ao dono como proposta de venda. Regras:\n"
    "- Arquivos: index.html, style.css e script.js nesta pasta. Nada de framework, npm ou build; abre direto no "
    "navegador e funciona no GitHub Pages. Fontes do Google Fonts podem ser usadas; nenhum outro arquivo externo.\n"
    "- Português do Brasil, celular primeiro (360px sem rolagem lateral), acessível (textos alternativos nas fotos, "
    "contraste, navegação por teclado), carregamento leve (loading=\"lazy\" nas fotos).\n"
    "- Seções: topo fixo com o nome e menu; abertura (hero) usando a melhor foto, com chamada forte e botão de "
    "WhatsApp; sobre; serviços (adequados ao ramo); galeria com TODAS as fotos de fotos/ e ampliação ao clicar "
    "(lightbox com setas e fechar no Esc); nota do Google (use a nota e o número de avaliações reais, se houver); "
    "localização com o mapa do Google incorporado e o endereço; contato; rodapé. Botão flutuante do WhatsApp.\n"
    "- Interatividade de verdade: menu que vira hambúrguer no celular, animações suaves ao rolar, galeria com "
    "lightbox, botão de voltar ao topo. Use o estilo de design pedido.\n"
    "- Links de contato: use o campo whatsapp de dados.json (https://wa.me/...) e, se não houver, o link_maps.\n"
    "- OBRIGATÓRIO: uma faixa fina no topo dizendo 'Prévia de demonstração · site não oficial de <nome>' e "
    "<meta name=\"robots\" content=\"noindex, nofollow\"> no head (o dono ainda não aprovou).\n"
    "- NUNCA invente depoimentos, preços, prêmios, anos de experiência ou dados que não estejam em dados.json; "
    "escreva textos gerais e verdadeiros para o ramo.\n"
    "- Não mexa em nada fora desta pasta e não apague as fotos.\n"
    "Ao terminar, responda com uma frase curta em português do Brasil, sem markdown, dizendo o que fez."
)


def _locais_quebrados(pasta_site, html_texto):
    """Arquivos locais citados no site (src/href) que não existem na pasta."""
    quebrados = []
    for caminho in re.findall(r"""(?:src|href)\s*=\s*["']([^"'#?]+)""", html_texto):
        if re.match(r"(?i)(?:https?:|mailto:|tel:|data:|javascript:|//)", caminho) or not caminho.strip():
            continue
        if not os.path.exists(os.path.join(pasta_site, urllib.parse.unquote(caminho).lstrip("./").replace("/", os.sep))):
            quebrados.append(caminho)
    return quebrados


def checar_site(pasta_site, item):
    """Lista de problemas do site (vazia = aprovado). É o que faz o loop pedir correção ao Claude."""
    index = os.path.join(pasta_site, "index.html")
    if not os.path.exists(index):
        return ["não existe index.html na pasta"]
    with open(index, encoding="utf-8", errors="replace") as arquivo:
        texto = arquivo.read()
    for extra in ("style.css", "script.js"):
        if os.path.exists(os.path.join(pasta_site, extra)):
            with open(os.path.join(pasta_site, extra), encoding="utf-8", errors="replace") as arquivo:
                texto_extra = arquivo.read()
            texto += texto_extra if extra == "script.js" else ""
    problemas = []
    if len(texto) < 9000:
        problemas.append("o site está curto demais: faltam seções (hero, sobre, serviços, galeria, nota, localização, contato)")
    if "noindex" not in texto:
        problemas.append('falta <meta name="robots" content="noindex, nofollow">')
    if "prévia" not in texto.lower() and "previa" not in texto.lower():
        problemas.append("falta a faixa 'Prévia de demonstração · site não oficial'")
    zap = prospeccao.whatsapp_de(item.get("telefone"))
    if zap and f"wa.me/{zap}" not in texto:
        problemas.append(f"os botões de contato precisam usar https://wa.me/{zap}")
    fotos = [f for f in os.listdir(os.path.join(pasta_site, "fotos"))] if os.path.isdir(os.path.join(pasta_site, "fotos")) else []
    usadas = [f for f in fotos if f in texto]
    if fotos and len(usadas) < min(len(fotos), 3):
        problemas.append(f"use as fotos de fotos/ na galeria e no topo (há {len(fotos)}, o site usa {len(usadas)})")
    quebrados = _locais_quebrados(pasta_site, texto)
    if quebrados:
        problemas.append("arquivos citados que não existem: " + ", ".join(quebrados[:6]))
    return problemas


GRAVES = ("arquivos citados que não existem", "não existe index.html", "o site está curto demais")


def _defeito_grave(problemas):
    """Problemas que deixam o site quebrado na tela (não só incompleto): aí é melhor outro caminho."""
    return any(p.startswith(GRAVES) for p in problemas or [])


def site_pelo_claude(item, busca, pasta_site, modelo, avisar, tentativas=3, skin=None):
    """O Claude Code constrói o site completo; a checagem reprova e manda corrigir, até `tentativas` voltas.
    Devolve (caminho do index.html, problemas que sobraram) ou (None, motivo) se o Claude não puder."""
    import claude_code
    if not claude_code.disponivel():
        return None, ["o Claude Code não está instalado"]
    achado = re.search(r",\s*([^,]+?)\s*-\s*[A-Z]{2}\b", item.get("endereco") or "")
    zap = prospeccao.whatsapp_de(item.get("telefone"))
    fotos = sorted(os.listdir(os.path.join(pasta_site, "fotos"))) if os.path.isdir(os.path.join(pasta_site, "fotos")) else []
    dados = {
        "nome": item["nome"], "ramo": item.get("categoria") or busca, "cidade": achado.group(1) if achado else "",
        "endereco": item.get("endereco", ""), "telefone": item.get("telefone", ""),
        "whatsapp": f"https://wa.me/{zap}" if zap else "", "nota_google": item.get("nota", ""),
        "avaliacoes_google": item.get("avaliacoes", ""), "link_maps": item.get("link_maps", ""),
        "fotos": [f"fotos/{f}" for f in fotos],
        "estilo_de_design": skin["descricao"] if skin else
        f"{modelo}: {MODELOS[modelo]['descricao']} (cor de destaque {MODELOS[modelo]['destaque']})",
    }
    os.makedirs(pasta_site, exist_ok=True)
    with open(os.path.join(pasta_site, "dados.json"), "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=1)
    pedido = (f"Construa o site completo de {item['nome']} ({dados['ramo']}), no estilo {dados['estilo_de_design']}. "
              "Leia dados.json e use as fotos da pasta fotos/.")
    problemas = []
    for tentativa in range(1, tentativas + 1):
        avisar(f"Claude construindo o site ({tentativa}/{tentativas}) · {item['nome'][:40]}")
        deu_certo, resposta = claude_code._rodar(
            pedido, pasta_site,
            {"instrucoes": INSTRUCOES_SITE,
             "extras": ["--permission-mode", "acceptEdits", "--allowedTools", "Read", "Glob", "Grep", "TodoWrite"]},
            25 * 60, avisar)
        if not deu_certo and not os.path.exists(os.path.join(pasta_site, "index.html")):
            return None, [f"o Claude não conseguiu ({(resposta or 'sem resposta')[:120]})"]
        problemas = checar_site(pasta_site, item)
        log.info("Fábrica de sites: %s, volta %d, problemas: %s", item["nome"], tentativa, problemas or "nenhum")
        if not problemas:
            break
        if not deu_certo:
            # o Claude parou no meio (geralmente o limite de uso da conta): insistir só gasta tempo
            log.warning("Fábrica de sites: o Claude parou no meio do site de %s; sem novas voltas", item["nome"])
            break
        pedido = ("A checagem automática do Jarvis reprovou o site desta pasta. Corrija TODOS estes problemas, sem "
                  "estragar o que já está bom: " + "; ".join(problemas))
    return os.path.join(pasta_site, "index.html"), problemas


def site_pela_reserva(item, pasta_site, avisar, tentativas=2):
    """Sem Claude (assinatura acabou, por exemplo): uma IA de reserva do .env escreve o site num arquivo só,
    que passa pela mesma checagem. Devolve (caminho, problemas) ou (None, motivo)."""
    import ia
    if not ia.configurados():
        return None, ["nenhuma IA de reserva configurada no .env"]
    with open(os.path.join(pasta_site, "dados.json"), encoding="utf-8") as arquivo:
        dados = arquivo.read()
    instrucoes = (INSTRUCOES_SITE.replace("index.html, style.css e script.js nesta pasta",
                                          "um único index.html com o CSS e o JavaScript dentro dele")
              + "\nResponda SOMENTE com o código HTML completo, começando em <!doctype html>.")
    pedido = f"dados.json:\n{dados}\n\nConstrua o site."
    problemas = []
    for tentativa in range(1, tentativas + 1):
        avisar(f"IA de reserva construindo o site ({tentativa}/{tentativas}) · {item['nome'][:40]}")
        resposta, provedor = ia.responder(pedido, instrucoes, limite=300)
        if not resposta:
            return None, ["as IAs de reserva não responderam"]
        inicio = resposta.lower().find("<!doctype")
        fim = resposta.lower().rfind("</html>")
        if inicio < 0 or fim < 0:
            problemas = ["a resposta não veio em HTML"]
            continue
        with open(os.path.join(pasta_site, "index.html"), "w", encoding="utf-8") as arquivo:
            arquivo.write(resposta[inicio:fim + 7])
        problemas = checar_site(pasta_site, item)
        log.info("Fábrica de sites: %s feito pela reserva %s, problemas: %s", item["nome"], provedor, problemas or "nenhum")
        if not problemas:
            break
        pedido = (f"dados.json:\n{dados}\n\nO site abaixo foi reprovado na checagem. Corrija estes problemas e "
                  f"devolva o HTML completo: {'; '.join(problemas)}\n\n{resposta[inicio:fim + 7]}")
    caminho = os.path.join(pasta_site, "index.html")
    return (caminho, problemas) if os.path.exists(caminho) else (None, problemas)


def print_do_site(caminho_html, destino):
    """Foto do site pronto (para a página de entregas e para o zip)."""
    navegador.abrir("file:///" + caminho_html.replace("\\", "/"))

    def foto():
        pagina = navegador._pagina()
        pagina.wait_for_timeout(1500)
        return navegador._foto(pagina, "png")

    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with open(destino, "wb") as arquivo:
        arquivo.write(navegador._rodar(foto, limite=60))
    return destino


# ---------- 6. zip ----------
def empacotar(pasta_negocio, destino_zip):
    """Zip com o site e os prints, para entregar ao cliente ou subir em qualquer hospedagem."""
    with zipfile.ZipFile(destino_zip, "w", zipfile.ZIP_DEFLATED) as pacote:
        for subpasta in ("site", "prints"):
            raiz = os.path.join(pasta_negocio, subpasta)
            for atual, _, arquivos in os.walk(raiz):
                if ".git" in atual.split(os.sep):
                    continue
                for nome in arquivos:
                    caminho = os.path.join(atual, nome)
                    pacote.write(caminho, os.path.relpath(caminho, pasta_negocio))
    return destino_zip


# ---------- 7. mensagem ----------
def mensagem(item, preco=None):
    quem = prospeccao._quem_sou()
    apresentacao = f"Aqui é da {quem}. " if quem else ""
    livre = next((d["dominio"] for d in item.get("dominios", []) if d["situacao"] == "livre"), "")
    link = f" Dá para ver aqui: {item['publicado']}" if item.get("publicado") else ""
    dominio = f" O endereço {livre} ainda está livre, se quiserem garantir." if livre else ""
    valor = f" O site completo, no ar, sai por R$ {preco}." if preco else ""
    return (f"Olá, tudo bem? {apresentacao}Vi que a {item['nome']} ainda não tem site e montei uma prévia, pensada "
            f"para trazer clientes pelo celular, com botão direto para o WhatsApp de vocês.{link}{dominio}{valor} "
            f"Posso te mandar um vídeo rápido mostrando? Se não tiver interesse, é só avisar que não mando mais nada.")


# ---------- página de entregas ----------
def _arquivo(caminho):
    return "file:///" + caminho.replace("\\", "/") if caminho else "#"


def pagina_de_entregas(execucao):
    e = html.escape
    cartoes = []
    for n, item in enumerate(execucao["itens"], 1):
        texto = mensagem(item, execucao.get("preco"))
        zap = prospeccao.whatsapp_de(item.get("telefone"))
        abrir = (f"<a class='zap' href='https://wa.me/{zap}?text={urllib.parse.quote(texto)}'>Abrir no WhatsApp</a>"
                 if zap else "<span class='sem'>sem celular no Maps</span>")
        dominios = " · ".join(f"{e(d['dominio'])} <i class='{e(d['situacao'].split()[0])}'>{e(d['situacao'])}</i>"
                              for d in item.get("dominios", []))
        publicado = (f"<a href='{e(item['publicado'])}'>{e(item['publicado'])}</a>" if item.get("publicado")
                     else "ainda não publicado")
        cartoes.append(f"""
<article>
  <h2>{n}. {e(item['nome'])}</h2>
  <p class="dados">{e(item.get('categoria') or '')} · ★ {e(item.get('nota') or '—')} · {e(item.get('telefone') or 'sem telefone')}
     · modelo <b>{e(item['modelo'])}</b> · site feito {'pelo <b>Claude</b>' if item.get('feito_por') == 'Claude' else 'pelo modelo pronto'}
     · {item.get('fotos', 0)} fotos<br>{e(item.get('endereco') or '')}</p>
  {('<p class="alerta">A checagem ainda viu: ' + e('; '.join(item['problemas'])) + '</p>') if item.get('problemas') else ''}
  <div class="prints">{''.join(f'<a href="{e(_arquivo(item[c]))}"><img src="{e(_arquivo(item[c]))}" alt="{r}"><span>{r}</span></a>'
                               for c, r in (('print_maps', 'Google Maps'), ('print_site', 'Site pronto')) if item.get(c))}</div>
  <p class="links"><a href="{e(_arquivo(item['site']))}">Ver o site</a> · <a href="{e(_arquivo(item.get('print_maps')))}">Print do Google Maps</a>
     · <a href="{e(_arquivo(item.get('zip')))}">Zip</a> · {f'<a href="{e(_arquivo(item["video"]))}">Vídeo MP4</a>' if item.get('video') else 'sem vídeo'}</p>
  <p class="links">Domínios: {dominios or '—'}<br>No ar: {publicado}</p>
  <textarea>{e(texto)}</textarea>
  <div class="acoes"><button onclick="copiar(this)">Copiar mensagem</button>{abrir}<label><input type="checkbox"> enviado</label></div>
</article>""")
    pagina = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Sites · {e(execucao['busca'])}</title>
<style>
  body {{ font-family: "Segoe UI", system-ui, sans-serif; background: #0b1220; color: #e2e8f0; margin: 0; padding: 32px 6vw; }}
  h1 {{ color: #38e1ff; }} .aviso {{ background: #1e293b; border-left: 4px solid #f59e0b; padding: 14px 18px; margin: 18px 0 28px; }}
  article {{ background: #111a2e; border: 1px solid #1f2b45; border-radius: 16px; padding: 22px; margin-bottom: 18px; }}
  .dados {{ opacity: .75; margin: 6px 0 10px; }} a {{ color: #38e1ff; }}
  .prints {{ display: flex; gap: 14px; flex-wrap: wrap; margin: 8px 0 12px; }}
  .prints a {{ display: flex; flex-direction: column; gap: 4px; text-decoration: none; font-size: 13px; }}
  .prints img {{ width: 300px; max-width: 100%; border-radius: 10px; border: 1px solid #334155; }}
  .alerta {{ color: #fbbf24; }}
  i.livre {{ color: #4ade80; font-style: normal; }} i.registrado {{ color: #f87171; font-style: normal; }} i.não {{ color: #fbbf24; font-style: normal; }}
  textarea {{ width: 100%; min-height: 100px; margin: 12px 0; background: #0b1220; color: #e2e8f0; border: 1px solid #334155; border-radius: 10px; padding: 10px; font: inherit; }}
  .acoes {{ display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }}
  button, .zap {{ border: 0; border-radius: 999px; padding: 10px 18px; font: inherit; font-weight: 700; text-decoration: none; cursor: pointer; }}
  button {{ background: #38e1ff; color: #04101b; }} .zap {{ background: #25d366; color: #04101b; }} .sem {{ opacity: .6; }}
</style></head><body>
<h1>Fábrica de sites: {e(execucao['busca'])}</h1>
<p>{len(execucao['itens'])} negócios sem site · gerado pelo Jarvis em {e(execucao['quando'])}</p>
{(lambda v: f'<p>Vídeos MP4 salvos no seu notebook em: <a href="{e(_arquivo(v))}">{e(v)}</a></p>' if v else '')(
    next((os.path.dirname(i["video"]) for i in execucao["itens"] if i.get("video")), ""))}
<div class="aviso">Cada site tem a faixa "prévia de demonstração" e não aparece no Google até o cliente aprovar. As fotos do
Google Maps estão só no print: peça ao cliente as fotos dele antes de colocar no site. Envie as mensagens uma por uma,
depois de conferir; disparo automático em massa é proibido pelo WhatsApp e pode banir o seu número.</div>
{''.join(cartoes)}
<script>
function copiar(botao) {{
  const texto = botao.closest('article').querySelector('textarea').value;
  navigator.clipboard.writeText(texto).then(() => {{ botao.textContent = 'Copiado!'; setTimeout(() => botao.textContent = 'Copiar mensagem', 1500); }});
}}
</script></body></html>"""
    caminho = os.path.join(execucao["pasta"], "entregas.html")
    with open(caminho, "w", encoding="utf-8") as arquivo:
        arquivo.write(pagina)
    return caminho


def _salvar(execucao):
    with open(os.path.join(execucao["pasta"], "sites.json"), "w", encoding="utf-8") as arquivo:
        json.dump(execucao, arquivo, ensure_ascii=False, indent=1)


def carregar(pasta):
    with open(os.path.join(pasta, "sites.json"), encoding="utf-8") as arquivo:
        return json.load(arquivo)


def pendentes_de_publicar():
    """[(pasta, quantos sites ainda não publicados)] de todas as levas da fábrica, da mais nova para a mais velha."""
    resultado = []
    for nome in sorted(os.listdir(SAIDA) if os.path.isdir(SAIDA) else [], reverse=True):
        pasta = os.path.join(SAIDA, nome)
        if not os.path.isfile(os.path.join(pasta, "sites.json")):
            continue
        try:
            faltam = sum(1 for i in carregar(pasta)["itens"] if not i.get("publicado"))
        except (OSError, ValueError, KeyError):
            continue
        if faltam:
            resultado.append((pasta, faltam))
    return resultado


def ultima_execucao():
    pastas = sorted(p for p in (os.listdir(SAIDA) if os.path.isdir(SAIDA) else [])
                    if os.path.isfile(os.path.join(SAIDA, p, "sites.json")))
    return os.path.join(SAIDA, pastas[-1]) if pastas else None


# ---------- tudo junto ----------
def executar(busca, quantidade=PADRAO, ao_evento=None, gravar=True, com_claude=True, preco=None,
             confirmar_web=False, skins=False):
    """Do Google Maps até a página de entregas (sem publicar). Devolve o resumo da execução.
    com_claude: o site completo é feito pelo Claude (minutos por site); False usa só o modelo pronto (segundos).
    preco: valor do site (R$) que entra na mensagem de cada cliente (código /700).
    confirmar_web: antes de fazer o site, pesquisa nome e telefone na web para confirmar que não tem site.
    skins: cada comércio ganha um skin novo do ramo (cores, fontes e formas próprias) em vez do modelo fixo."""
    avisar = ao_evento or (lambda t: None)
    quantidade = max(1, min(quantidade, MAXIMO))
    agora = datetime.datetime.now()
    pasta = os.path.join(SAIDA, f"{agora:%Y-%m-%d-%H%M}-{_slug(busca)}")
    os.makedirs(pasta, exist_ok=True)
    negocios = buscar_sem_site(busca, quantidade * 2 if confirmar_web else quantidade, avisar)
    descartados = []
    if confirmar_web:
        cidade = (re.search(r"\bem\s+(.+)$", busca, re.I) or [None, ""])[1]
        confirmados = []
        for negocio in negocios:
            if len(confirmados) >= quantidade:
                break
            sem, motivo = confirmar_sem_site(negocio, cidade, avisar)
            log.info("Fábrica de sites: %s -> %s", negocio["nome"], motivo)
            (confirmados if sem else descartados).append(negocio if sem else {"nome": negocio["nome"], "motivo": motivo})
        negocios = confirmados
    if not negocios:
        raise ValueError(f"Não achei negócios sem site para '{busca}'. Tente outro ramo ou cidade.")
    execucao = {"busca": busca, "quando": f"{agora:%d/%m/%Y %H:%M}", "pasta": pasta, "itens": [], "preco": preco,
                "descartados": descartados}
    pasta_videos = os.path.join(VIDEOS, os.path.basename(pasta))
    for n, negocio in enumerate(negocios, 1):
        nome = negocio["nome"]
        slug = _slug(nome)
        pasta_negocio = os.path.join(pasta, slug)
        item = {**negocio, "slug": slug}
        avisar(f"{n}/{len(negocios)} · print do Google Maps · {nome[:40]}")
        try:
            item["print_maps"] = print_do_maps(negocio, os.path.join(pasta_negocio, "prints", "google-maps.png"))
        except Exception:
            log.warning("Fábrica de sites: sem print de %s", nome, exc_info=True)
            item["print_maps"] = ""
        pasta_site = os.path.join(pasta_negocio, "site")
        avisar(f"{n}/{len(negocios)} · baixando as fotos · {nome[:40]}")
        try:  # a página do negócio ainda está aberta, do print
            item["fotos"] = len(baixar_fotos(os.path.join(pasta_site, "fotos")))
        except Exception:
            log.warning("Fábrica de sites: sem fotos de %s", nome, exc_info=True)
            item["fotos"] = 0
        avisar(f"{n}/{len(negocios)} · conferindo domínios · {nome[:40]}")
        achado = re.search(r",\s*([^,]+?)\s*-\s*[A-Z]{2}\b", negocio.get("endereco") or "")
        item["dominios"] = verificar_dominios(nome, achado.group(1) if achado else "")
        item["modelo"] = escolher_modelo(f"{negocio.get('categoria', '')} {busca}")
        skin = skin_novo(f"{negocio.get('categoria') or ''} {busca}".strip(), nome) if skins else None
        if skin:
            item["skin"] = skin
        item["site"], item["problemas"], item["feito_por"] = None, [], "modelo"
        if com_claude:
            try:
                item["site"], item["problemas"] = site_pelo_claude(item, busca, pasta_site, item["modelo"], avisar,
                                                                   skin=skin)
                item["feito_por"] = "Claude" if item["site"] else "modelo"
            except Exception:
                log.exception("Fábrica de sites: o Claude falhou no site de %s", nome)
            if item["site"] and _defeito_grave(item["problemas"]):
                log.warning("Fábrica de sites: site de %s saiu quebrado pelo Claude (%s); tentando a reserva",
                            nome, item["problemas"])
                item["site"] = None
            if not item["site"]:  # sem Claude: tenta uma IA de reserva (Gemini, Groq, OpenAI, Ollama)
                try:
                    item["site"], item["problemas"] = site_pela_reserva(item, pasta_site, avisar)
                    item["feito_por"] = "IA de reserva" if item["site"] else "modelo"
                except Exception:
                    log.exception("Fábrica de sites: a IA de reserva falhou no site de %s", nome)
                if item["site"] and _defeito_grave(item["problemas"]):
                    log.warning("Fábrica de sites: site de %s saiu quebrado pela reserva; usando o modelo", nome)
                    item["site"] = None
        if not item["site"]:  # sem nenhuma IA: o modelo pronto garante que sempre sai um site
            avisar(f"{n}/{len(negocios)} · montando o site pelo modelo {item['modelo']} · {nome[:40]}")
            item["site"] = construir_site(negocio, busca, pasta_site, item["modelo"], skin)
            item["problemas"] = []
        try:
            item["print_site"] = print_do_site(item["site"], os.path.join(pasta_negocio, "prints", "site.png"))
        except Exception:
            log.warning("Fábrica de sites: sem print do site de %s", nome, exc_info=True)
            item["print_site"] = ""
        item["video"] = ""
        if gravar:
            avisar(f"{n}/{len(negocios)} · gravando o vídeo · {nome[:40]}")
            try:
                item["video"] = prospeccao.gravar_video(item["site"], os.path.join(pasta_videos, slug + ".mp4"))
            except Exception:
                log.warning("Fábrica de sites: falha no vídeo de %s", nome, exc_info=True)
        item["zip"] = empacotar(pasta_negocio, os.path.join(pasta, slug + ".zip"))
        item["publicado"] = ""
        execucao["itens"].append(item)
        _salvar(execucao)  # salva a cada negócio: se algo travar, o que já foi feito fica
    execucao["pasta_videos"] = execucao["pasta_envio"] = pasta_videos
    _salvar(execucao)
    execucao["entregas"] = pagina_de_entregas(execucao)
    _pacote(execucao)
    log.info("Fábrica de sites '%s': %d sites em %s", busca, len(execucao["itens"]), pasta)
    return execucao


def _pacote(execucao):
    """Contatos (.txt e Excel), vídeos MP4 e página de entregas juntos na pasta dos vídeos."""
    pasta = execucao.get("pasta_envio") or execucao.get("pasta_videos") or os.path.join(
        VIDEOS, os.path.basename(execucao["pasta"]))
    execucao["pasta_envio"] = pasta
    pagina = execucao.get("entregas") or os.path.join(execucao["pasta"], "entregas.html")
    return prospeccao.pacote_de_envio(pasta, execucao["busca"], execucao["itens"],
                                      [mensagem(i, execucao.get("preco")) for i in execucao["itens"]], pagina)


def publicar(pasta, ao_evento=None):
    """Publica no GitHub Pages os sites da execução (chamar só depois do "sim" do usuário)."""
    import github_pages
    avisar = ao_evento or (lambda t: None)
    execucao = carregar(pasta)
    publicados = 0
    for item in execucao["itens"]:
        if item.get("publicado"):
            continue
        avisar(f"Publicando {item['nome'][:40]} no GitHub")
        repo = f"previa-{item['slug']}"[:90]
        try:
            item["publicado"] = github_pages.publicar(os.path.dirname(item["site"]), repo,
                                                      f"Prévia do site de {item['nome']}")
            publicados += 1
        except Exception:
            log.exception("Falha ao publicar %s", item["nome"])
        _salvar(execucao)
    execucao["entregas"] = pagina_de_entregas(execucao)
    _pacote(execucao)  # as mensagens agora levam o link do site no ar
    _salvar(execucao)
    return publicados, execucao
