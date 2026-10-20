"""Prospecção completa (código B/107108109110 300-300): comércios do Google Maps -> prévia de site para cada um ->
vídeo da prévia -> página com as mensagens prontas para o usuário enviar.

O Jarvis NÃO envia as mensagens sozinho: disparo automático em massa no WhatsApp (Premium Sender e afins) é
proibido pelo WhatsApp, costuma banir o número de quem envia e esbarra na LGPD. A página de envios deixa cada
mensagem a um clique ("Abrir no WhatsApp" já abre a conversa com o texto escrito); o usuário confere, anexa o
vídeo e envia, um por um.

A lista e as prévias ficam em prospeccao/<busca>/ (negocios.csv, previas/<comércio>/index.html, envios.html).
Os vídeos MP4 ficam na pasta Vídeos do notebook: Vídeos\\Jarvis\\Prospecção\\<busca>\\<comércio>.mp4.
"""
import csv
import datetime
import hashlib
import html
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
import unicodedata
import urllib.parse

import navegador

PASTA = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(PASTA, "prospeccao")


def pasta_videos():
    """A pasta Vídeos do Windows (onde ela estiver de verdade), para os MP4 ficarem fáceis de achar."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as chave:
            caminho = os.path.expandvars(winreg.QueryValueEx(chave, "My Video")[0])
        if os.path.isdir(caminho):
            return caminho
    except OSError:
        pass
    return os.path.join(os.path.expanduser("~"), "Videos")


VIDEOS = os.path.join(pasta_videos(), "Jarvis", "Prospecção")
MEUS_DADOS = os.path.join(PASTA, "biblioteca", "meus_dados.md")
PADRAO_NEGOCIOS = 5
MAX_NEGOCIOS = 15
SEGUNDOS_DE_VIDEO = 14
QUADROS_POR_SEGUNDO = 10

log = logging.getLogger("jarvis")


def _slug(texto):
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", texto).strip("-")[:50] or "comercio"


# ---------- 1. Google Maps ----------
_JS_LISTA = r"""() => {
  const vistos = new Set(), itens = [];
  for (const a of document.querySelectorAll('a[href*="/maps/place/"]')) {
    const nome = (a.getAttribute('aria-label') || '').trim();
    if (!nome || vistos.has(nome)) continue;
    vistos.add(nome);
    itens.push({nome, link: a.href});
  }
  return itens;
}"""

_JS_ROLAR_LISTA = r"""() => { const f = document.querySelector('div[role=feed]'); if (f) f.scrollBy(0, 1500); return !!f; }"""

_JS_DETALHES = r"""() => {
  const rotulo = (sel) => { const el = document.querySelector(sel); return el ? (el.getAttribute('aria-label') || el.innerText || '').trim() : ''; };
  const limpar = (t) => t.replace(/^[^:]{0,20}:\s*/, '').trim();
  const nota = document.querySelector('div.F7nice span[aria-hidden="true"]');
  const avals = [...document.querySelectorAll('div.F7nice span[aria-label]')].map(e => e.getAttribute('aria-label')).join(' ');
  return {
    nome: (document.querySelector('h1') || {}).innerText || '',
    categoria: (document.querySelector('button[jsaction*="category"]') || {}).innerText || '',
    telefone: limpar(rotulo('button[data-item-id^="phone"]')),
    endereco: limpar(rotulo('button[data-item-id="address"]')),
    site: (document.querySelector('a[data-item-id="authority"]') || {}).href || '',
    nota: nota ? nota.innerText.trim() : '',
    avaliacoes: (avals.match(/[\d.]+/) || [''])[0].replace(/\./g, ''),
  };
}"""


def buscar_negocios(busca, quantidade=PADRAO_NEGOCIOS, ao_evento=None):
    """Comércios da busca no Google Maps, lidos na mini tela: [{nome, telefone, endereco, site, nota, ...}]."""
    avisar = ao_evento or (lambda t: None)
    quantidade = max(1, min(quantidade, MAX_NEGOCIOS))
    avisar("Procurando no Google Maps")
    navegador.abrir("https://www.google.com/maps/search/" + urllib.parse.quote(busca))

    def lista():
        pagina = navegador._pagina()
        try:
            pagina.wait_for_selector('a[href*="/maps/place/"], h1', timeout=25000)
        except Exception:
            pass
        itens = pagina.evaluate(_JS_LISTA)
        for _ in range(6):  # a lista do Maps carrega mais resultados conforme rola
            if len(itens) >= quantidade or not pagina.evaluate(_JS_ROLAR_LISTA):
                break
            pagina.wait_for_timeout(1500)
            itens = pagina.evaluate(_JS_LISTA)
        if not itens and "/maps/place/" in pagina.url:  # a busca caiu direto num lugar só
            itens = [{"nome": "", "link": pagina.url}]
        return itens[:quantidade]

    itens = navegador._rodar(lista, limite=90)
    if not itens:
        raise ValueError(f"O Google Maps não mostrou resultados para '{busca}'.")

    negocios = []
    for n, item in enumerate(itens, 1):
        avisar(f"Lendo {n}/{len(itens)} · {item['nome'][:50]}")

        def detalhes(link=item["link"]):
            pagina = navegador._pagina()
            pagina.goto(link, wait_until="commit", timeout=40000)
            try:
                pagina.wait_for_selector("h1", timeout=20000)
                pagina.wait_for_timeout(1200)
            except Exception:
                pass
            return pagina.evaluate(_JS_DETALHES)

        try:
            dados = navegador._rodar(detalhes, limite=70)
        except Exception:
            log.warning("Prospecção: não consegui ler %s", item["link"], exc_info=True)
            dados = {}
        dados["nome"] = (dados.get("nome") or item["nome"]).strip()
        dados["link_maps"] = item["link"]
        if dados["nome"]:
            negocios.append({k: (v or "").strip() if isinstance(v, str) else v for k, v in dados.items()})
    return negocios


def whatsapp_de(telefone):
    """Número no formato do wa.me (55 + DDD + número), ou "" se não der para entender."""
    digitos = re.sub(r"\D", "", telefone or "")
    if digitos.startswith("0"):
        digitos = digitos.lstrip("0")
    if len(digitos) in (10, 11):
        digitos = "55" + digitos
    return digitos if len(digitos) in (12, 13) and digitos.startswith("55") else ""


# ---------- 2. prévia do site ----------
SERVICOS = {
    "barbearia": ["Corte masculino", "Barba na navalha", "Sobrancelha", "Pigmentação"],
    "salao": ["Corte e escova", "Coloração", "Manicure e pedicure", "Tratamentos capilares"],
    "restaurante": ["Almoço executivo", "Pratos à la carte", "Delivery", "Eventos e reservas"],
    "pizzaria": ["Pizzas tradicionais", "Pizzas especiais", "Delivery rápido", "Combos para a família"],
    "lanchonete": ["Lanches artesanais", "Porções", "Bebidas geladas", "Delivery"],
    "academia": ["Musculação", "Treino funcional", "Avaliação física", "Planos flexíveis"],
    "oficina": ["Revisão completa", "Freios e suspensão", "Troca de óleo", "Diagnóstico eletrônico"],
    "auto": ["Revisão completa", "Freios e suspensão", "Troca de óleo", "Diagnóstico eletrônico"],
    "clinica": ["Consultas", "Exames", "Atendimento humanizado", "Agendamento fácil"],
    "dentista": ["Limpeza e prevenção", "Clareamento", "Ortodontia", "Implantes"],
    "pet": ["Banho e tosa", "Consultas veterinárias", "Rações e acessórios", "Leva e traz"],
    "loja": ["Novidades toda semana", "Atendimento personalizado", "Entrega na cidade", "Parcelamento"],
}
PALETAS = [("#0f172a", "#38bdf8"), ("#1c1917", "#f59e0b"), ("#111827", "#34d399"), ("#18181b", "#f472b6"),
           ("#0c0a09", "#fb923c"), ("#020617", "#a78bfa")]


def _servicos(texto):
    t = _slug(texto)
    for chave, lista in SERVICOS.items():
        if chave in t:
            return lista
    return ["Atendimento de qualidade", "Preço justo", "Atendimento rápido", "Fale com a gente pelo WhatsApp"]


def gerar_previa(negocio, busca, pasta):
    """Página de demonstração do site do comércio, a partir de um modelo (não gasta crédito do Claude)."""
    nome = negocio["nome"]
    fundo, destaque = PALETAS[int(hashlib.md5(nome.encode()).hexdigest(), 16) % len(PALETAS)]
    ramo = negocio.get("categoria") or busca
    # "Av. Dois de Junho, 2660 - Centro, Cacoal - RO, 76963-854" -> "Cacoal"
    achado = re.search(r",\s*([^,]+?)\s*-\s*[A-Z]{2}\b", negocio.get("endereco") or "")
    cidade = achado.group(1).strip() if achado else ""
    zap = whatsapp_de(negocio.get("telefone"))
    contato = f"https://wa.me/{zap}" if zap else (negocio.get("link_maps") or "#")
    iniciais = "".join(p[0] for p in re.findall(r"\w+", nome)[:2]).upper() or "★"
    nota = negocio.get("nota") or ""
    avaliacoes = negocio.get("avaliacoes") or ""
    e = html.escape
    servicos = "".join(f"<div class='card'><span>✦</span><h3>{e(s)}</h3></div>" for s in _servicos(f"{ramo} {busca}"))
    mapa = ("https://www.google.com/maps?output=embed&q=" + urllib.parse.quote(f"{nome} {negocio.get('endereco', '')}"))
    estrelas = f"<div class='nota'>★ {e(nota)}<small>{e(avaliacoes)} avaliações no Google</small></div>" if nota else ""
    pagina = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(nome)}</title>
<style>
  :root {{ --fundo: {fundo}; --destaque: {destaque}; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: "Segoe UI", system-ui, sans-serif; background: var(--fundo); color: #f8fafc; line-height: 1.5; }}
  header {{ display: flex; align-items: center; justify-content: space-between; padding: 22px 7vw; }}
  .marca {{ display: flex; gap: 12px; align-items: center; font-weight: 700; font-size: 20px; }}
  .logo {{ width: 46px; height: 46px; border-radius: 14px; display: grid; place-items: center; background: var(--destaque);
           color: var(--fundo); font-weight: 800; }}
  .botao {{ display: inline-block; padding: 14px 26px; border-radius: 999px; background: var(--destaque); color: var(--fundo);
            font-weight: 700; text-decoration: none; box-shadow: 0 10px 30px color-mix(in srgb, var(--destaque) 40%, transparent); }}
  .hero {{ padding: 90px 7vw 110px; background: radial-gradient(circle at 80% 20%, color-mix(in srgb, var(--destaque) 30%, transparent), transparent 55%); }}
  .hero p.tag {{ color: var(--destaque); font-weight: 600; letter-spacing: .12em; text-transform: uppercase; font-size: 14px; }}
  .hero h1 {{ font-size: clamp(38px, 6vw, 72px); line-height: 1.05; margin: 14px 0 18px; max-width: 900px; }}
  .hero p.sub {{ font-size: 20px; opacity: .8; max-width: 640px; margin-bottom: 34px; }}
  .nota {{ display: inline-flex; flex-direction: column; margin-left: 22px; vertical-align: middle; font-size: 26px; font-weight: 700; color: #fde047; }}
  .nota small {{ font-size: 13px; color: #cbd5e1; font-weight: 400; }}
  section {{ padding: 80px 7vw; }}
  section h2 {{ font-size: 34px; margin-bottom: 30px; }}
  .grade {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 18px; }}
  .card {{ padding: 28px; border-radius: 20px; background: rgba(255,255,255,.05); border: 1px solid rgba(255,255,255,.08); }}
  .card span {{ color: var(--destaque); font-size: 22px; }}
  .card h3 {{ margin-top: 12px; font-size: 19px; }}
  .local {{ display: grid; grid-template-columns: 1fr 1.3fr; gap: 30px; align-items: center; }}
  .local iframe {{ width: 100%; height: 320px; border: 0; border-radius: 20px; }}
  footer {{ padding: 40px 7vw; opacity: .6; font-size: 14px; text-align: center; }}
  @media (max-width: 760px) {{ .local {{ grid-template-columns: 1fr; }} .nota {{ margin: 20px 0 0; display: flex; }} }}
</style></head>
<body>
<header><div class="marca"><div class="logo">{e(iniciais)}</div>{e(nome)}</div>
  <a class="botao" href="{e(contato)}">Fale conosco</a></header>
<div class="hero">
  <p class="tag">{e(ramo)}{(' em ' + e(cidade)) if cidade else ''}</p>
  <h1>{e(nome)}</h1>
  <p class="sub">Qualidade, atendimento de verdade e tudo o que você precisa, agora a um clique de distância.</p>
  <a class="botao" href="{e(contato)}">Chamar no WhatsApp</a>{estrelas}
</div>
<section><h2>O que oferecemos</h2><div class="grade">{servicos}</div></section>
<section><div class="local"><div><h2>Onde estamos</h2><p>{e(negocio.get('endereco') or 'Consulte nosso endereço pelo WhatsApp.')}</p>
  <p style="margin-top:12px">{e(negocio.get('telefone') or '')}</p></div>
  <iframe loading="lazy" src="{e(mapa)}"></iframe></div></section>
<footer>Prévia de site criada para {e(nome)} · demonstração</footer>
</body></html>"""
    destino = os.path.join(pasta, "previas", _slug(nome))
    os.makedirs(destino, exist_ok=True)
    caminho = os.path.join(destino, "index.html")
    with open(caminho, "w", encoding="utf-8") as arquivo:
        arquivo.write(pagina)
    return caminho


# ---------- 3. vídeo da prévia ----------
def gravar_video(caminho_html, destino_mp4, segundos=SEGUNDOS_DE_VIDEO, ao_evento=None):
    """Abre a prévia na mini tela, rola devagar até o fim e grava em MP4 (fotos da mini tela + ffmpeg)."""
    import imageio_ffmpeg
    navegador.abrir("file:///" + caminho_html.replace("\\", "/"))
    time.sleep(1.5)
    altura = navegador._rodar(lambda: navegador._pagina().evaluate(
        "() => Math.max(0, document.documentElement.scrollHeight - innerHeight)"), limite=20)
    quadros = tempfile.mkdtemp(prefix="jarvis_video_")
    try:
        # Quadro por quadro, num ritmo fixo (e não "em tempo real"): com o PC ocupado a gravação só demora mais,
        # mas o vídeo sai sempre suave (antes, com o Claude rodando junto, saía com 2 quadros por segundo).
        fps = QUADROS_POR_SEGUNDO
        total = segundos * fps
        inicio = time.time()
        for n in range(total):
            fracao = n / (total - 1)
            # devagar no começo e no fim, para a rolagem ficar natural
            posicao = int(altura * (fracao * fracao * (3 - 2 * fracao)))

            def foto(y=posicao):
                pagina = navegador._pagina()
                pagina.evaluate(f"window.scrollTo({{top: {y}, behavior: 'instant'}})")
                pagina.wait_for_timeout(40)  # deixa as animações de "aparecer ao rolar" começarem
                return navegador._foto(pagina, "jpeg", 80)

            imagem = navegador._rodar(foto, limite=30)
            with open(os.path.join(quadros, f"q{n:05d}.jpg"), "wb") as arquivo:
                arquivo.write(imagem)
        n = total
        os.makedirs(os.path.dirname(destino_mp4), exist_ok=True)
        comando = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-framerate", str(fps),
                   "-i", os.path.join(quadros, "q%05d.jpg"), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                   "-vf", "scale=1280:-2", "-r", "30", destino_mp4]
        subprocess.run(comando, check=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        log.info("Prospecção: vídeo MP4 %s (%d quadros, %d por segundo, gravado em %.0f s)", destino_mp4, n, fps,
                 time.time() - inicio)
        return destino_mp4
    finally:
        shutil.rmtree(quadros, ignore_errors=True)


# ---------- pasta de envio: tudo num lugar só, fácil de achar ----------
def pacote_de_envio(pasta, titulo, itens, textos, pagina_html=None):
    """Na pasta dos vídeos MP4 cria "CONTATOS PARA ENVIAR.txt" e contatos.csv (abre no Excel) com nome, telefone,
    link do WhatsApp, mensagem e o vídeo de cada um, e copia a página de envios. Devolve a pasta."""
    os.makedirs(pasta, exist_ok=True)
    linhas = [f"ENVIOS - {titulo}", f"Gerado pelo Jarvis em {datetime.datetime.now():%d/%m/%Y %H:%M}", "",
              "Como enviar: abra o WhatsApp do contato (link abaixo), copie e cole a mensagem, anexe o vídeo indicado",
              "(ele está nesta mesma pasta) e envie. Atalho: o arquivo 'ABRIR - página de envios' tem um botão que já",
              "abre a conversa com a mensagem escrita. Um por um: envio automático em massa é proibido pelo WhatsApp",
              "e pode banir o seu número. Se alguém pedir para não receber, respeite.", ""]
    planilha = []
    for n, (item, texto) in enumerate(zip(itens, textos), 1):
        zap = whatsapp_de(item.get("telefone"))
        # link curto (no Bloco de Notas o link nem é clicável; o com a mensagem escrita fica na página de envios)
        link = f"https://wa.me/{zap}" if zap else ""
        video = os.path.basename(item.get("video") or "")
        linhas += [f"{n}) {item['nome']}",
                   f"   Telefone: {item.get('telefone') or 'não aparece no Google Maps'}",
                   f"   WhatsApp: {link or 'sem celular no Google Maps (ligue ou procure no Instagram)'}",
                   f"   Vídeo para mandar: {video or 'não foi gravado'}"]
        if item.get("publicado"):
            linhas.append(f"   Site no ar: {item['publicado']}")
        linhas += ["   Mensagem:", *[f"   {parte}" for parte in texto.split("\n")], ""]
        planilha.append({"numero": n, "nome": item["nome"], "telefone": item.get("telefone", ""),
                         "whatsapp": f"https://wa.me/{zap}" if zap else "", "video": video,
                         "site_publicado": item.get("publicado", ""), "mensagem": texto, "enviado": ""})
    with open(os.path.join(pasta, "CONTATOS PARA ENVIAR.txt"), "w", encoding="utf-8-sig") as arquivo:
        arquivo.write("\n".join(linhas))
    with open(os.path.join(pasta, "contatos.csv"), "w", encoding="utf-8-sig", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=list(planilha[0].keys()) if planilha else ["nome"], delimiter=";")
        escritor.writeheader()
        escritor.writerows(planilha)
    if pagina_html and os.path.exists(pagina_html):
        shutil.copy2(pagina_html, os.path.join(pasta, "ABRIR - página de envios.html"))
    return pasta


def atalho_na_area_de_trabalho(pasta, nome="Jarvis - Envios"):
    """Atalho na Área de Trabalho para a pasta (sempre o mesmo nome, apontando para a última). Devolve o caminho."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as chave:
            area = os.path.expandvars(winreg.QueryValueEx(chave, "Desktop")[0])
    except OSError:
        area = os.path.join(os.path.expanduser("~"), "Desktop")
    destino = os.path.join(area, nome + ".lnk")
    script = ("$a = (New-Object -ComObject WScript.Shell).CreateShortcut($env:JARVIS_LNK); "
              "$a.TargetPath = $env:JARVIS_ALVO; $a.Description = 'Pasta de envios do Jarvis'; $a.Save()")
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", script], check=True, timeout=30,
                       env={**os.environ, "JARVIS_LNK": destino, "JARVIS_ALVO": pasta},
                       capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        return destino
    except (OSError, subprocess.SubprocessError):
        # sem PowerShell (antivírus bloqueou, por exemplo): um atalho de internet também abre a pasta
        log.warning("Atalho .lnk falhou; criando atalho .url", exc_info=True)
        destino = os.path.join(area, nome + ".url")
        with open(destino, "w", encoding="utf-8") as arquivo:
            arquivo.write(f"[InternetShortcut]\nURL=file:///{pasta.replace(os.sep, '/')}\n")
        return destino


# ---------- 4. mensagens e página de envios ----------
def _quem_sou():
    """Nome/marca do usuário em biblioteca/meus_dados.md, se ele preencheu."""
    try:
        with open(MEUS_DADOS, encoding="utf-8") as arquivo:
            # [ \t]* e não \s*: com o campo vazio, \s* pulava a linha e pegava o campo de baixo
            achado = re.search(r"Nome da empresa / marca:[ \t]*([^\n]*)", arquivo.read())
        return achado.group(1).strip() if achado and achado.group(1).strip() else ""
    except OSError:
        return ""


def mensagem(negocio):
    quem = _quem_sou()
    apresentacao = f"Aqui é da {quem}. " if quem else ""
    nota = f", com nota {negocio['nota']}," if negocio.get("nota") else ""
    return (f"Olá, tudo bem? {apresentacao}Vi a {negocio['nome']} no Google Maps{nota} e preparei uma prévia de site "
            f"para vocês, pensada para trazer mais clientes pelo celular. Posso te mandar um vídeo rápido de como "
            f"ficou? Se não tiver interesse, é só me avisar que não mando mais nada.")


def pagina_de_envios(busca, negocios, pasta):
    e = html.escape
    cartoes = []
    for n, negocio in enumerate(negocios, 1):
        texto = mensagem(negocio)
        zap = whatsapp_de(negocio.get("telefone"))
        abrir = (f"<a class='botao' href='https://wa.me/{zap}?text={urllib.parse.quote(texto)}'>Abrir no WhatsApp</a>"
                 if zap else "<span class='sem'>sem celular no Maps</span>")
        video = negocio.get("video")
        cartoes.append(f"""
<article>
  <h2>{n}. {e(negocio['nome'])}</h2>
  <p class="dados">{e(negocio.get('categoria') or '')} · ★ {e(negocio.get('nota') or '—')} · {e(negocio.get('telefone') or 'sem telefone')}<br>
     {e(negocio.get('endereco') or '')}</p>
  <p class="links"><a href="{e(_arquivo(negocio['previa']))}">Ver prévia</a>
     {f'· <a href="{e(_arquivo(video))}">Vídeo</a> ({e(os.path.basename(video))})' if video else '· vídeo não gravado'}
     · <a href="{e(negocio.get('link_maps', '#'))}">Google Maps</a>
     {f'· <a href="{e(negocio["site"])}">site atual</a>' if negocio.get('site') else '· <b>não tem site</b>'}</p>
  <textarea>{e(texto)}</textarea>
  <div class="acoes"><button onclick="copiar(this)">Copiar mensagem</button>{abrir}
    <label><input type="checkbox"> enviado</label></div>
</article>""")
    pagina = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Envios · {e(busca)}</title>
<style>
  body {{ font-family: "Segoe UI", system-ui, sans-serif; background: #0b1220; color: #e2e8f0; margin: 0; padding: 32px 6vw; }}
  h1 {{ color: #38e1ff; margin-bottom: 6px; }} .aviso {{ background: #1e293b; border-left: 4px solid #f59e0b; padding: 14px 18px; margin: 18px 0 28px; }}
  article {{ background: #111a2e; border: 1px solid #1f2b45; border-radius: 16px; padding: 22px; margin-bottom: 18px; }}
  .dados {{ opacity: .75; margin: 6px 0 10px; }} .links a {{ color: #38e1ff; }}
  textarea {{ width: 100%; min-height: 96px; margin: 12px 0; background: #0b1220; color: #e2e8f0; border: 1px solid #334155;
              border-radius: 10px; padding: 10px; font: inherit; }}
  .acoes {{ display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }}
  button, .botao {{ background: #38e1ff; color: #04101b; border: 0; border-radius: 999px; padding: 10px 18px; font-weight: 700;
                    text-decoration: none; cursor: pointer; font: inherit; font-weight: 700; }}
  .botao {{ background: #25d366; }} .sem {{ opacity: .6; }}
</style></head><body>
<h1>Prospecção: {e(busca)}</h1>
<p>{len(negocios)} comércios · gerado pelo Jarvis em {datetime.datetime.now():%d/%m/%Y %H:%M}</p>
{(lambda v: f'<p>Vídeos MP4 salvos no seu notebook em: <a href="{e(_arquivo(v))}">{e(v)}</a></p>' if v else '')(
    next((os.path.dirname(n["video"]) for n in negocios if n.get("video")), ""))}
<div class="aviso">Envie um por um, depois de conferir: <b>Abrir no WhatsApp</b> abre a conversa com a mensagem escrita;
anexe o vídeo e envie. Disparo automático em massa é proibido pelo WhatsApp e pode banir o seu número.
Respeite quem pedir para não receber mais mensagens.</div>
{''.join(cartoes)}
<script>
function copiar(botao) {{
  const texto = botao.closest('article').querySelector('textarea').value;
  navigator.clipboard.writeText(texto).then(() => {{ botao.textContent = 'Copiado!'; setTimeout(() => botao.textContent = 'Copiar mensagem', 1500); }});
}}
</script></body></html>"""
    caminho = os.path.join(pasta, "envios.html")
    with open(caminho, "w", encoding="utf-8") as arquivo:
        arquivo.write(pagina)
    return caminho


def _arquivo(caminho):
    return "file:///" + caminho.replace("\\", "/") if caminho else "#"


def _salvar_lista(negocios, pasta):
    campos = ["nome", "categoria", "telefone", "whatsapp", "endereco", "site", "nota", "avaliacoes", "link_maps",
              "previa", "video"]
    with open(os.path.join(pasta, "negocios.csv"), "w", encoding="utf-8-sig", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=campos, extrasaction="ignore", delimiter=";")
        escritor.writeheader()
        for negocio in negocios:
            escritor.writerow({**negocio, "whatsapp": whatsapp_de(negocio.get("telefone"))})
    with open(os.path.join(pasta, "negocios.json"), "w", encoding="utf-8") as arquivo:
        json.dump(negocios, arquivo, ensure_ascii=False, indent=1)


# ---------- tudo junto ----------
def executar(busca, quantidade=PADRAO_NEGOCIOS, ao_evento=None, gravar=True):
    """Prospecção completa. Devolve {"pasta", "envios", "negocios", "videos", "com_whatsapp"}."""
    avisar = ao_evento or (lambda t: None)
    pasta = os.path.join(SAIDA, f"{datetime.datetime.now():%Y-%m-%d-%H%M}-{_slug(busca)}")
    os.makedirs(pasta, exist_ok=True)
    negocios = buscar_negocios(busca, quantidade, avisar)
    if not negocios:
        raise ValueError("Não consegui ler os comércios no Google Maps.")
    for n, negocio in enumerate(negocios, 1):
        avisar(f"Prévia {n}/{len(negocios)} · {negocio['nome'][:50]}")
        negocio["previa"] = gerar_previa(negocio, busca, pasta)
    videos = 0
    pasta_mp4 = os.path.join(VIDEOS, os.path.basename(pasta))  # Vídeos\Jarvis\Prospecção\<data-busca>
    if gravar:
        for n, negocio in enumerate(negocios, 1):
            avisar(f"Gravando vídeo {n}/{len(negocios)} · {negocio['nome'][:50]}")
            try:
                negocio["video"] = gravar_video(negocio["previa"],
                                                os.path.join(pasta_mp4, _slug(negocio["nome"]) + ".mp4"))
                videos += 1
            except Exception:
                log.warning("Prospecção: falha ao gravar o vídeo de %s", negocio["nome"], exc_info=True)
                negocio["video"] = ""
    _salvar_lista(negocios, pasta)
    envios = pagina_de_envios(busca, negocios, pasta)
    # tudo de enviar (vídeos MP4, contatos em .txt e .csv, página) na mesma pasta, fácil de achar
    pacote_de_envio(pasta_mp4, busca, negocios, [mensagem(n) for n in negocios], envios)
    log.info("Prospecção '%s': %d comércios, %d vídeos, em %s", busca, len(negocios), videos, pasta)
    return {"pasta": pasta, "envios": envios, "negocios": len(negocios), "videos": videos, "pasta_videos": pasta_mp4,
            "pasta_envio": pasta_mp4, "com_whatsapp": sum(1 for n in negocios if whatsapp_de(n.get("telefone")))}
