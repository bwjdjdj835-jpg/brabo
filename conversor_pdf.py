"""Conversor de PDF do Jarvis: junta até 100 arquivos em um PDF só.

Aceita textos e códigos (txt, md, py, js, html, kt, json...), fotos e prints, PDFs, Word (.docx) e ZIP
(lista o conteúdo e inclui os códigos de dentro). O PDF sai com um sumário no começo e um marcador por
arquivo, pronto para mandar para o Claude ler. Vídeos, APKs e outros binários ficam de fora (e aparecem
no sumário com o motivo).
"""
import datetime
import io
import logging
import os
import re
import unicodedata
import zipfile

from defusedxml import ElementTree
from fpdf import FPDF
from fpdf.enums import WrapMode, XPos, YPos
from PIL import Image, ImageOps
from pypdf import PdfReader, PdfWriter

PASTA = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(PASTA, "pdfs")
LIMITE_ARQUIVOS = 100
LIMITE_MB = 200                # por arquivo
LIMITE_CARACTERES = 400_000    # por arquivo de texto: código minificado gigante viraria milhares de páginas
LIMITE_ZIP_CARACTERES = 1_500_000
FONTES = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")

IMAGENS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".ico"}
CODIGOS = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".html", ".htm", ".css", ".scss", ".json",
           ".xml", ".kt", ".kts", ".java", ".gradle", ".properties", ".bat", ".cmd", ".ps1", ".sh", ".yml",
           ".yaml", ".toml", ".ini", ".cfg", ".sql", ".c", ".cpp", ".h", ".cs", ".go", ".rs", ".php", ".rb",
           ".swift", ".dart", ".vue", ".svelte", ".svg", ".csv", ".log", ".env", ".gitignore"}
TEXTOS = {".txt", ".md", ".markdown", ".rtf"}
PASTAS_IGNORADAS_ZIP = ("node_modules/", ".git/", "build/", ".gradle/", "__pycache__/", ".venv/", "dist/")

# Arquivos do próprio Jarvis que NÃO entram no PDF: senha do e-mail e histórico de conversas
JARVIS_FORA = {"email_config.json", "memoria.json", ".env", ".env.exemplo", "telegram_ids.json"}

log = logging.getLogger("jarvis")
# avisos de letra sem desenho na fonte (emojis) e de recorte de fonte enchem o registro
logging.getLogger("fpdf").setLevel(logging.ERROR)
logging.getLogger("fontTools").setLevel(logging.ERROR)
logging.getLogger("pypdf").setLevel(logging.ERROR)  # PDF inválido já vira motivo no sumário


class _Pular(Exception):
    """O arquivo não entra no PDF; a mensagem é o motivo, mostrado no sumário."""


class _Pdf(FPDF):
    def __init__(self):
        super().__init__(format="A4")
        self.set_margins(14, 14, 14)
        self.set_auto_page_break(True, margin=14)
        self.unicode = self._carregar_fontes()

    def _carregar_fontes(self):
        arquivos = {("sans", ""): "arial.ttf", ("sans", "B"): "arialbd.ttf", ("mono", ""): "consola.ttf"}
        if not all(os.path.exists(os.path.join(FONTES, f)) for f in arquivos.values()):
            return False
        for (familia, estilo), arquivo in arquivos.items():
            self.add_font(familia, estilo, os.path.join(FONTES, arquivo))
        simbolos = os.path.join(FONTES, "seguisym.ttf")
        if os.path.exists(simbolos):
            self.add_font("simbolos", "", simbolos)
            self.set_fallback_fonts(["simbolos"])
        return True

    def fonte(self, familia, estilo="", tamanho=10):
        if not self.unicode:
            familia = {"sans": "helvetica", "mono": "courier"}[familia]
        self.set_font(familia, estilo, tamanho)

    def limpar(self, texto):
        texto = texto.replace("\r\n", "\n").replace("\r", "\n").expandtabs(4)
        texto = "".join(c for c in texto if c == "\n" or unicodedata.category(c)[0] != "C")
        if not self.unicode:
            texto = texto.encode("latin-1", "replace").decode("latin-1")
        return texto

    def escrever(self, altura, texto, wrapmode=WrapMode.WORD):
        self.multi_cell(0, altura, texto, wrapmode=wrapmode, new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _tamanho(n):
    for unidade in ("B", "KB", "MB"):
        if n < 1024:
            return f"{n:.0f} {unidade}"
        n /= 1024
    return f"{n:.1f} GB"


def _ler_texto(dados):
    """Bytes para texto; None se parecer binário."""
    if b"\x00" in dados[:8192]:
        return None
    for codificacao in ("utf-8-sig", "cp1252"):
        try:
            return dados.decode(codificacao)
        except UnicodeDecodeError:
            pass
    return dados.decode("latin-1")


def _texto_docx(dados):
    w = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(io.BytesIO(dados)) as pacote:
        raiz = ElementTree.fromstring(pacote.read("word/document.xml"))
    paragrafos = []
    for paragrafo in raiz.iter(w + "p"):
        partes = []
        for no in paragrafo.iter():
            if no.tag == w + "t":
                partes.append(no.text or "")
            elif no.tag == w + "tab":
                partes.append("\t")
            elif no.tag in (w + "br", w + "cr"):
                partes.append("\n")
        paragrafos.append("".join(partes))
    return "\n".join(paragrafos)


# ---------- páginas ----------
def _cabecalho(pdf, titulo, detalhe):
    pdf.add_page()
    pdf.fonte("sans", "B", 13)
    pdf.escrever(6.5, pdf.limpar(titulo), WrapMode.CHAR)
    pdf.fonte("sans", "", 8.5)
    pdf.set_text_color(110)
    pdf.escrever(4.5, pdf.limpar(detalhe), WrapMode.CHAR)
    pdf.set_text_color(0)
    pdf.set_draw_color(190)
    pdf.line(pdf.l_margin, pdf.get_y() + 1, pdf.w - pdf.r_margin, pdf.get_y() + 1)
    pdf.ln(4)


def _corpo(pdf, texto, codigo, limite=LIMITE_CARACTERES):
    texto = pdf.limpar(texto)
    cortado = len(texto) > limite
    texto = texto[:limite]
    if not texto.strip():
        texto = "(arquivo vazio)"
    linhas = texto.split("\n")
    if codigo:
        # número da linha na frente: dá para dizer "muda a linha 120 do app.py"
        largura = len(str(len(linhas)))
        linhas = [f"{n:>{largura}}  {linha}" for n, linha in enumerate(linhas, 1)]
        pdf.fonte("mono", "", 7.8)
        altura, quebra = 3.8, WrapMode.CHAR
    else:
        pdf.fonte("sans", "", 10)
        altura, quebra = 5, WrapMode.WORD
    for i in range(0, len(linhas), 200):
        pdf.escrever(altura, "\n".join(linhas[i:i + 200]), quebra)
    if cortado:
        pdf.ln(3)
        pdf.fonte("sans", "B", 9)
        pdf.escrever(5, f"[Arquivo muito grande: só os primeiros {limite:,} caracteres entraram no PDF.]".replace(",", "."))


def _imagem(pdf, dados, titulo, detalhe):
    try:
        imagem = Image.open(io.BytesIO(dados))
        imagem.load()
    except Exception as erro:
        raise _Pular(f"imagem ilegível ({erro})")
    imagem = ImageOps.exif_transpose(imagem)
    if imagem.mode in ("RGBA", "LA", "P"):
        imagem = imagem.convert("RGBA")
        fundo = Image.new("RGB", imagem.size, "white")
        fundo.paste(imagem, mask=imagem.split()[-1])
        imagem = fundo
    elif imagem.mode != "RGB":
        imagem = imagem.convert("RGB")
    imagem.thumbnail((2200, 2200))
    _cabecalho(pdf, titulo, f"{detalhe} · {imagem.width}x{imagem.height}px")
    largura_max = pdf.epw
    altura_max = pdf.h - pdf.get_y() - pdf.b_margin
    proporcao = imagem.height / imagem.width
    largura = min(largura_max, altura_max / proporcao)
    pdf.image(imagem, x=pdf.l_margin + (largura_max - largura) / 2, y=pdf.get_y(),
              w=largura, h=largura * proporcao)


def _zip(pdf, dados, titulo, detalhe):
    try:
        pacote = zipfile.ZipFile(io.BytesIO(dados))
    except zipfile.BadZipFile:
        raise _Pular("ZIP corrompido")
    with pacote:
        membros = [m for m in pacote.infolist() if not m.is_dir()]
        listagem = "\n".join(f"{m.filename}  ({_tamanho(m.file_size)})" for m in membros[:3000])
        _cabecalho(pdf, titulo, f"{detalhe} · ZIP com {len(membros)} arquivos")
        pdf.fonte("sans", "B", 10)
        pdf.escrever(5, "Conteúdo do ZIP")
        _corpo(pdf, listagem, codigo=False)
        restante = LIMITE_ZIP_CARACTERES
        for membro in membros:
            nome = membro.filename
            extensao = os.path.splitext(nome)[1].lower()
            if (any("/" + p in "/" + nome for p in PASTAS_IGNORADAS_ZIP)
                    or extensao not in CODIGOS | TEXTOS or membro.file_size > 2 * 1024 * 1024):
                continue
            if restante <= 0:
                break
            texto = _ler_texto(pacote.read(membro))
            if texto is None:
                continue
            _cabecalho(pdf, f"{titulo} › {nome}", f"dentro do ZIP · {_tamanho(membro.file_size)}")
            _corpo(pdf, texto, codigo=extensao in CODIGOS, limite=min(LIMITE_CARACTERES, restante))
            restante -= len(texto)


def _converter(pdf, caminho, titulo):
    """Põe o arquivo no PDF gerado (devolve None) ou devolve o PdfReader de um PDF pronto."""
    if not os.path.isfile(caminho):
        raise _Pular("arquivo não encontrado")
    tamanho = os.path.getsize(caminho)
    if tamanho > LIMITE_MB * 1024 * 1024:
        raise _Pular(f"passa de {LIMITE_MB} MB")
    extensao = os.path.splitext(caminho)[1].lower()
    quando = datetime.datetime.fromtimestamp(os.path.getmtime(caminho)).strftime("%d/%m/%Y %H:%M")
    detalhe = f"{caminho} · {_tamanho(tamanho)} · modificado em {quando}"

    if extensao == ".pdf":
        try:
            leitor = PdfReader(caminho)
            if leitor.is_encrypted and not leitor.decrypt(""):
                raise _Pular("PDF protegido por senha")
            if not len(leitor.pages):
                raise _Pular("PDF sem páginas")
        except _Pular:
            raise
        except Exception as erro:
            raise _Pular(f"PDF ilegível ({erro})")
        return leitor

    with open(caminho, "rb") as arquivo:
        dados = arquivo.read()
    if extensao in IMAGENS:
        _imagem(pdf, dados, titulo, detalhe)
    elif extensao == ".docx":
        try:
            texto = _texto_docx(dados)
        except Exception as erro:
            raise _Pular(f"Word ilegível ({erro})")
        _cabecalho(pdf, titulo, detalhe)
        _corpo(pdf, texto, codigo=False)
    elif extensao == ".zip":
        _zip(pdf, dados, titulo, detalhe)
    else:
        texto = _ler_texto(dados)
        if texto is None:
            raise _Pular("tipo de arquivo que não vira texto (vídeo, APK, programa...)")
        _cabecalho(pdf, titulo, detalhe)
        _corpo(pdf, texto, codigo=extensao in CODIGOS or extensao not in TEXTOS)
    return None


def _sumario(titulo, partes, pulados, paginas_sumario):
    pdf = _Pdf()
    pdf.add_page()
    total = paginas_sumario + sum(p["paginas"] for p in partes)
    pdf.fonte("sans", "B", 9)
    pdf.set_text_color(0, 150, 190)
    pdf.escrever(5, "J.A.R.V.I.S. · PDF")
    pdf.set_text_color(0)
    pdf.fonte("sans", "B", 18)
    pdf.escrever(9, pdf.limpar(titulo))
    pdf.fonte("sans", "", 9)
    pdf.set_text_color(110)
    pdf.escrever(5, f"Gerado em {datetime.datetime.now():%d/%m/%Y %H:%M} · {len(partes)} arquivos · {total} páginas")
    pdf.set_text_color(0)
    pdf.ln(5)
    pdf.fonte("sans", "B", 12)
    pdf.escrever(7, "Sumário")
    pdf.fonte("sans", "", 9.5)
    pagina = paginas_sumario + 1
    for n, parte in enumerate(partes, 1):
        nome = pdf.limpar(f"{n}. {parte['titulo']}")
        while pdf.get_string_width(nome) > pdf.epw - 22 and len(nome) > 10:
            nome = nome[:-2]
        pdf.cell(pdf.epw - 20, 5.5, nome)
        pdf.cell(20, 5.5, str(pagina), align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pagina += parte["paginas"]
    if pulados:
        pdf.ln(5)
        pdf.fonte("sans", "B", 12)
        pdf.escrever(7, "Ficaram de fora")
        pdf.fonte("sans", "", 9.5)
        for nome, motivo in pulados:
            pdf.escrever(5, pdf.limpar(f"• {nome}: {motivo}"), WrapMode.CHAR)
    return pdf


def _nome_arquivo(titulo):
    base = unicodedata.normalize("NFKD", titulo).encode("ascii", "ignore").decode()
    base = re.sub(r"[^\w\-]+", "-", base).strip("-").lower()[:50] or "arquivos"
    return f"{base}-{datetime.datetime.now():%Y-%m-%d-%H%M%S}.pdf"


def juntar(caminhos, titulo="Arquivos", base=None, ao_progresso=None):
    """Junta até 100 arquivos em um PDF. Devolve {arquivo, paginas, convertidos, pulados}.

    base: pasta usada para mostrar os nomes relativos (ex.: interface/index.html).
    ao_progresso(n, total, nome): chamado antes de cada arquivo.
    """
    caminhos = list(dict.fromkeys(os.path.abspath(c) for c in caminhos))
    pulados = [(os.path.basename(c), f"passou do limite de {LIMITE_ARQUIVOS} arquivos")
               for c in caminhos[LIMITE_ARQUIVOS:]]
    caminhos = caminhos[:LIMITE_ARQUIVOS]

    gerado = _Pdf()
    partes = []
    for n, caminho in enumerate(caminhos, 1):
        nome = os.path.relpath(caminho, base).replace("\\", "/") if base else os.path.basename(caminho)
        if ao_progresso:
            ao_progresso(n, len(caminhos), nome)
        inicio = gerado.page
        try:
            leitor = _converter(gerado, caminho, nome)
        except _Pular as motivo:
            pulados.append((nome, str(motivo)))
            continue
        except Exception as erro:
            log.exception("Falha ao converter %s para PDF", caminho)
            pulados.append((nome, f"erro ao converter ({erro})"))
            continue
        if leitor is not None:
            partes.append({"titulo": nome, "leitor": leitor, "paginas": len(leitor.pages)})
        elif gerado.page > inicio:
            partes.append({"titulo": nome, "intervalo": (inicio, gerado.page), "paginas": gerado.page - inicio})
    if not partes:
        raise ValueError("Nenhum dos arquivos pôde ser convertido para PDF.")

    # o sumário vai na frente, então os números de página dependem do tamanho dele
    paginas_sumario = 1
    while True:
        sumario = _sumario(titulo, partes, pulados, paginas_sumario)
        if sumario.page == paginas_sumario:
            break
        paginas_sumario = sumario.page

    escritor = PdfWriter()
    escritor.append(PdfReader(io.BytesIO(bytes(sumario.output()))), outline_item="Sumário")
    leitor_gerado = PdfReader(io.BytesIO(bytes(gerado.output()))) if gerado.page else None
    for parte in partes:
        if "leitor" in parte:
            escritor.append(parte["leitor"], outline_item=parte["titulo"], import_outline=False)
        else:
            escritor.append(leitor_gerado, outline_item=parte["titulo"], pages=parte["intervalo"],
                            import_outline=False)
    escritor.add_metadata({"/Title": titulo, "/Creator": "J.A.R.V.I.S."})

    os.makedirs(SAIDA, exist_ok=True)
    destino = os.path.join(SAIDA, _nome_arquivo(titulo))
    with open(destino, "wb") as arquivo:
        escritor.write(arquivo)
    paginas = len(escritor.pages)
    log.info("PDF gerado: %s (%d arquivos, %d páginas, %d de fora)", destino, len(partes), paginas, len(pulados))
    return {"arquivo": destino, "paginas": paginas,
            "convertidos": [p["titulo"] for p in partes], "pulados": pulados}


def arquivos_do_jarvis():
    """O código do próprio Jarvis, para mandar ao Claude atualizar. Senha do e-mail e conversas ficam de fora."""
    caminhos = []
    for nome in sorted(os.listdir(PASTA)):
        caminho = os.path.join(PASTA, nome)
        if (os.path.isfile(caminho) and nome not in JARVIS_FORA
                and nome.lower().endswith((".py", ".bat", ".txt", ".md"))):
            caminhos.append(caminho)
    interface = os.path.join(PASTA, "interface")
    if os.path.isdir(interface):
        caminhos += [os.path.join(interface, n) for n in sorted(os.listdir(interface))
                     if os.path.isfile(os.path.join(interface, n))]
    instrucoes = os.path.join(PASTA, "projetos", "CLAUDE.md")
    if os.path.exists(instrucoes):
        caminhos.append(instrucoes)
    return caminhos
