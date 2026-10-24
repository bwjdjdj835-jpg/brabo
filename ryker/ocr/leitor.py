"""Leitura de texto na tela, com dois motores para medir e escolher (Fase 1).

- "windows": o OCR que já vem no Windows 10/11 (Windows.Media.Ocr), no idioma pt-BR. Leve e rápido.
- "rapid":   RapidOCR (modelos do PaddleOCR rodando no onnxruntime). Mais pesado; fica de reserva.

    palavras = ler(imagem_pil, motor="windows")
    # [{"texto": "Salvar", "caixa": (x, y, largura, altura), "confianca": None}, ...]

As caixas estão em pixels da imagem recebida. Os pacotes são importados só quando usados.
"""
import io
import logging

log = logging.getLogger("jarvis")
MOTORES = ("windows", "rapid")
_rapid = None


def ler(imagem, motor="windows", idioma="pt-BR", ampliar=1):
    """Palavras (windows) ou linhas (rapid) achadas na imagem PIL. ampliar=2 ajuda em letras pequenas de menu."""
    if ampliar != 1:
        imagem = imagem.resize((imagem.width * ampliar, imagem.height * ampliar))
    if motor == "windows":
        achados = _ler_windows(imagem, idioma)
    elif motor == "rapid":
        achados = _ler_rapid(imagem)
    else:
        raise ValueError(f"motor desconhecido: {motor}")
    if ampliar != 1:
        for a in achados:
            a["caixa"] = tuple(round(v / ampliar) for v in a["caixa"])
    return achados


def texto(achados):
    return " ".join(a["texto"] for a in achados)


# ---------- Windows OCR ----------
def idiomas_windows():
    from winrt.windows.media.ocr import OcrEngine
    return [l.language_tag for l in OcrEngine.available_recognizer_languages]


def _ler_windows(imagem, idioma):
    import asyncio
    return asyncio.run(_ler_windows_async(imagem, idioma))


async def _ler_windows_async(imagem, idioma):
    from winrt.windows.globalization import Language
    from winrt.windows.graphics.imaging import BitmapDecoder
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream

    limite = OcrEngine.max_image_dimension
    if max(imagem.size) > limite:  # o Windows recusa imagens maiores que isso
        escala = limite / max(imagem.size)
        imagem = imagem.resize((int(imagem.width * escala), int(imagem.height * escala)))
    else:
        escala = 1.0
    png = io.BytesIO()
    imagem.convert("RGB").save(png, "PNG")
    fluxo = InMemoryRandomAccessStream()
    escritor = DataWriter(fluxo)
    escritor.write_bytes(png.getvalue())
    await escritor.store_async()
    escritor.detach_stream()
    fluxo.seek(0)
    bitmap = await (await BitmapDecoder.create_async(fluxo)).get_software_bitmap_async()
    motor = OcrEngine.try_create_from_language(Language(idioma)) or OcrEngine.try_create_from_user_profile_languages()
    if motor is None:
        raise RuntimeError(f"Windows OCR sem o idioma {idioma}")
    resultado = await motor.recognize_async(bitmap)
    achados = []
    for linha in resultado.lines:
        for palavra in linha.words:
            r = palavra.bounding_rect
            achados.append({"texto": palavra.text, "confianca": None,
                            "caixa": tuple(round(v / escala) for v in (r.x, r.y, r.width, r.height))})
    return achados


# ---------- RapidOCR ----------
def _ler_rapid(imagem):
    global _rapid
    import numpy as np
    if _rapid is None:
        from rapidocr_onnxruntime import RapidOCR
        _rapid = RapidOCR()
    resultado, _tempo = _rapid(np.array(imagem.convert("RGB")))
    achados = []
    for caixa, texto_lido, confianca in resultado or []:
        xs, ys = [p[0] for p in caixa], [p[1] for p in caixa]
        achados.append({"texto": texto_lido, "confianca": round(float(confianca), 3),
                        "caixa": (round(min(xs)), round(min(ys)), round(max(xs) - min(xs)), round(max(ys) - min(ys)))})
    return achados
