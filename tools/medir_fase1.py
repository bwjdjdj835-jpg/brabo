"""Fase 1 do RYKER: mede, neste PC, a captura da tela (MSS x DXcam) e o OCR (Windows OCR x RapidOCR).

    python tools/medir_fase1.py            # mede tudo; cada candidato roda num processo separado (memória limpa)

Precisa de: mss, pillow, numpy, psutil, dxcam, rapidocr_onnxruntime e os pacotes winrt-Windows.Media.Ocr
(+ Graphics.Imaging, Storage.Streams, Globalization, Foundation). Dá para rodar num ambiente separado do Braga.
Só lê a tela: não clica nem digita nada.
"""
import json
import os
import statistics
import subprocess
import sys
import time
import unicodedata

PASTA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PASTA)

# texto de interface em pt-BR, com acentos, para conferir o que o OCR acerta
FRASES = [
    "Arquivo  Editar  Exibir  Inserir  Formatar  Ajuda",
    "Erro: não foi possível salvar o arquivo cadeira.blend",
    "Configurações de exibição  ·  Resolução 1920 × 1200",
    "Salvar como…   Cancelar   Concluído   Próximo",
    "Atenção: a operação falhou. Tente novamente.",
    "Área de Trabalho  Downloads  Documentos  Vídeos",
]
TAMANHOS = (12, 14, 18)  # px, como menus (12), texto comum (14) e títulos (18)


def _mb():
    import psutil
    return psutil.Process().memory_info().rss / 1024 ** 2


def _normalizar(t):
    return "".join(c for c in unicodedata.normalize("NFC", t.lower()) if c.isalnum() or c.isspace())


def imagem_de_teste():
    """Fundo claro e fundo escuro, cada frase em 3 tamanhos, com a fonte do Windows (Segoe UI)."""
    from PIL import Image, ImageDraw, ImageFont
    linhas = [(f, t, tema) for tema in ("claro", "escuro") for t in TAMANHOS for f in FRASES]
    imagem = Image.new("RGB", (1100, 28 + sum(t + 14 for _, t, _ in linhas)), "white")
    desenho = ImageDraw.Draw(imagem)
    y = 14
    for frase, tamanho, tema in linhas:
        fonte = ImageFont.truetype(r"C:\Windows\Fonts\segoeui.ttf", tamanho)
        fundo, cor = ("#ffffff", "#1b1b1b") if tema == "claro" else ("#1f2430", "#e6e6e6")
        desenho.rectangle((0, y - 6, 1100, y + tamanho + 8), fill=fundo)
        desenho.text((16, y), frase, font=fonte, fill=cor)
        y += tamanho + 14
    return imagem, linhas


def acerto(achados_texto, linhas):
    """Palavras certas (com acento) e palavras certas ignorando acento, sobre o total esperado."""
    lidas = _normalizar(achados_texto).split()
    sem = lambda p: "".join(c for c in unicodedata.normalize("NFD", p) if unicodedata.category(c) != "Mn")
    esperadas = [p for f, _, _ in linhas for p in _normalizar(f).split()]
    sobra, sobra_sem = list(lidas), [sem(p) for p in lidas]
    certas = certas_sem = 0
    for p in esperadas:
        if p in sobra:
            sobra.remove(p); certas += 1
        if sem(p) in sobra_sem:
            sobra_sem.remove(sem(p)); certas_sem += 1
    return round(100 * certas / len(esperadas), 1), round(100 * certas_sem / len(esperadas), 1)


# ---------- uma medição por processo ----------
def medir_captura(motor):
    import psutil
    from ryker.vision.captura import Captura
    antes = _mb()
    with Captura(motor) as cap:
        criar = _mb() - antes
        tempos, novas = [], 0
        for _ in range(40):  # o mais rápido possível
            t0 = time.perf_counter()
            imagem = cap.foto()
            tempos.append((time.perf_counter() - t0) * 1000)
            novas += imagem is not None
        # 6 s a 10 quadros por segundo, como o espelho do quarto: quanto de processador gasta
        proc = psutil.Process()
        cpu0, t_ini, quadros = proc.cpu_times(), time.perf_counter(), 0
        while time.perf_counter() - t_ini < 6:
            t0 = time.perf_counter()
            quadros += cap.foto() is not None
            time.sleep(max(0, 0.1 - (time.perf_counter() - t0)))
        cpu1, duracao = proc.cpu_times(), time.perf_counter() - t_ini
        cpu = (cpu1.user + cpu1.system - cpu0.user - cpu0.system) / duracao / psutil.cpu_count() * 100
        return {"motor": motor, "tela": f"{cap.monitor['width']}x{cap.monitor['height']}",
                "ms_media": round(statistics.mean(tempos), 1), "ms_p95": round(sorted(tempos)[37], 1),
                "fotos_novas_de_40": novas, "cpu_10fps_pct_do_pc": round(cpu, 2), "quadros_novos_em_6s": quadros,
                "memoria_mb": round(_mb() - antes, 1), "memoria_ao_criar_mb": round(criar, 1)}


def medir_ocr(motor):
    from ryker.ocr import leitor
    from ryker.vision.captura import Captura
    extra = {}
    if motor == "windows":
        extra["idiomas_do_windows"] = leitor.idiomas_windows()
    imagem, linhas = imagem_de_teste()
    antes = _mb()
    t0 = time.perf_counter()
    achados = leitor.ler(imagem, motor)
    frio = (time.perf_counter() - t0) * 1000
    quentes = []
    for _ in range(3):
        t0 = time.perf_counter(); achados = leitor.ler(imagem, motor); quentes.append((time.perf_counter() - t0) * 1000)
    com_acento, sem_acento = acerto(leitor.texto(achados), linhas)
    amp = leitor.ler(imagem, motor, ampliar=2)
    com_acento2, sem_acento2 = acerto(leitor.texto(amp), linhas)
    with Captura("mss") as cap:  # a tela de verdade, agora
        tela = cap.foto()
    t0 = time.perf_counter(); na_tela = leitor.ler(tela, motor); ms_tela = (time.perf_counter() - t0) * 1000
    janela = tela.crop((0, 0, tela.width // 2, tela.height // 2))  # um quarto da tela, como "a janela ativa"
    t0 = time.perf_counter(); leitor.ler(janela, motor); ms_janela = (time.perf_counter() - t0) * 1000
    return {"motor": motor, **extra, "ms_primeira": round(frio), "ms_teste": round(statistics.mean(quentes)),
            "acerto_pct": com_acento, "acerto_sem_acento_pct": sem_acento,
            "acerto_ampliado_2x_pct": com_acento2, "acerto_ampliado_2x_sem_acento_pct": sem_acento2,
            "ms_tela_inteira": round(ms_tela), "palavras_na_tela": len(na_tela),
            "ms_quarto_da_tela": round(ms_janela), "memoria_mb": round(_mb() - antes, 1),
            "exemplo_lido": leitor.texto(achados)[:160]}


def principal():
    resultados = []
    for tipo, motor in (("captura", "mss"), ("captura", "dxcam"), ("ocr", "windows"), ("ocr", "rapid")):
        print(f"medindo {tipo} {motor}...", flush=True)
        r = subprocess.run([sys.executable, __file__, tipo, motor], capture_output=True, text=True,
                           encoding="utf-8", timeout=600)
        try:
            resultados.append({"tipo": tipo, **json.loads(r.stdout.strip().splitlines()[-1])})
        except Exception:
            resultados.append({"tipo": tipo, "motor": motor, "erro": (r.stderr or r.stdout)[-600:]})
    saida = os.path.join(PASTA, "ryker", "medicoes_fase1.json")
    with open(saida, "w", encoding="utf-8") as f:
        json.dump({"data": time.strftime("%Y-%m-%d %H:%M"), "resultados": resultados}, f, ensure_ascii=False, indent=1)
    print(json.dumps(resultados, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    if len(sys.argv) == 3:
        funcao = medir_captura if sys.argv[1] == "captura" else medir_ocr
        sys.stdout.reconfigure(encoding="utf-8")
        print(json.dumps(funcao(sys.argv[2]), ensure_ascii=False))
    else:
        principal()
