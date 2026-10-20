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


def escolher_modelo(ramo):
    texto = _slug(ramo)
    for modelo, palavras in RAMOS_DOS_MODELOS.items():
        if any(p in texto for p in palavras):
            return modelo
    return "noturno"


# ---------- 5. o site ----------
def construir_site(negocio, busca, pasta_site, modelo):
    e = html.escape
    m = MODELOS[modelo]
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
def mensagem(item):
    quem = prospeccao._quem_sou()
    apresentacao = f"Aqui é da {quem}. " if quem else ""
    livre = next((d["dominio"] for d in item.get("dominios", []) if d["situacao"] == "livre"), "")
    link = f" Dá para ver aqui: {item['publicado']}" if item.get("publicado") else ""
    dominio = f" O endereço {livre} ainda está livre, se quiserem garantir." if livre else ""
    return (f"Olá, tudo bem? {apresentacao}Vi que a {item['nome']} ainda não tem site e montei uma prévia, pensada "
            f"para trazer clientes pelo celular, com botão direto para o WhatsApp de vocês.{link}{dominio} Posso te "
            f"mandar um vídeo rápido mostrando? Se não tiver interesse, é só avisar que não mando mais nada.")


# ---------- página de entregas ----------
def _arquivo(caminho):
    return "file:///" + caminho.replace("\\", "/") if caminho else "#"


def pagina_de_entregas(execucao):
    e = html.escape
    cartoes = []
    for n, item in enumerate(execucao["itens"], 1):
        texto = mensagem(item)
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
     · modelo <b>{e(item['modelo'])}</b><br>{e(item.get('endereco') or '')}</p>
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
  i.livre {{ color: #4ade80; font-style: normal; }} i.registrado {{ color: #f87171; font-style: normal; }} i.não {{ color: #fbbf24; font-style: normal; }}
  textarea {{ width: 100%; min-height: 100px; margin: 12px 0; background: #0b1220; color: #e2e8f0; border: 1px solid #334155; border-radius: 10px; padding: 10px; font: inherit; }}
  .acoes {{ display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }}
  button, .zap {{ border: 0; border-radius: 999px; padding: 10px 18px; font: inherit; font-weight: 700; text-decoration: none; cursor: pointer; }}
  button {{ background: #38e1ff; color: #04101b; }} .zap {{ background: #25d366; color: #04101b; }} .sem {{ opacity: .6; }}
</style></head><body>
<h1>Fábrica de sites: {e(execucao['busca'])}</h1>
<p>{len(execucao['itens'])} negócios sem site · gerado pelo Jarvis em {e(execucao['quando'])}</p>
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


def ultima_execucao():
    pastas = sorted(p for p in (os.listdir(SAIDA) if os.path.isdir(SAIDA) else [])
                    if os.path.isfile(os.path.join(SAIDA, p, "sites.json")))
    return os.path.join(SAIDA, pastas[-1]) if pastas else None


# ---------- tudo junto ----------
def executar(busca, quantidade=PADRAO, ao_evento=None, gravar=True):
    """Do Google Maps até a página de entregas (sem publicar). Devolve o resumo da execução."""
    avisar = ao_evento or (lambda t: None)
    quantidade = max(1, min(quantidade, MAXIMO))
    agora = datetime.datetime.now()
    pasta = os.path.join(SAIDA, f"{agora:%Y-%m-%d-%H%M}-{_slug(busca)}")
    os.makedirs(pasta, exist_ok=True)
    negocios = buscar_sem_site(busca, quantidade, avisar)
    if not negocios:
        raise ValueError(f"Não achei negócios sem site para '{busca}'. Tente outro ramo ou cidade.")
    execucao = {"busca": busca, "quando": f"{agora:%d/%m/%Y %H:%M}", "pasta": pasta, "itens": []}
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
        avisar(f"{n}/{len(negocios)} · conferindo domínios · {nome[:40]}")
        achado = re.search(r",\s*([^,]+?)\s*-\s*[A-Z]{2}\b", negocio.get("endereco") or "")
        item["dominios"] = verificar_dominios(nome, achado.group(1) if achado else "")
        item["modelo"] = escolher_modelo(f"{negocio.get('categoria', '')} {busca}")
        avisar(f"{n}/{len(negocios)} · construindo o site (modelo {item['modelo']}) · {nome[:40]}")
        item["site"] = construir_site(negocio, busca, os.path.join(pasta_negocio, "site"), item["modelo"])
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
    execucao["pasta_videos"] = pasta_videos
    _salvar(execucao)
    execucao["entregas"] = pagina_de_entregas(execucao)
    log.info("Fábrica de sites '%s': %d sites em %s", busca, len(execucao["itens"]), pasta)
    return execucao


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
    return publicados, execucao
