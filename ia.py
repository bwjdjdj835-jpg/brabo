"""IAs de reserva: quando o Claude não responde (assinatura acabou, sem internet para ele, limite de uso), o Jarvis
tenta estas outras, na ordem de JARVIS_IA_ORDEM no .env. Só entram as que tiverem chave (ou o Ollama ligado).

- gemini: Google Gemini (tem plano grátis; chave em https://aistudio.google.com/apikey)
- groq:   Groq (grátis e rápido; chave em https://console.groq.com/keys)
- openai: OpenAI / ChatGPT (pago; chave em https://platform.openai.com/api-keys)
- ollama: modelo rodando no próprio PC (https://ollama.com), sem chave e sem internet

As chaves ficam no .env (que não vai para o git nem para a biblioteca) e vão sempre no cabeçalho da requisição,
nunca no endereço. Sem nenhuma configurada, o Jarvis segue só com o Claude, como antes.
"""
import base64
import json
import logging
import urllib.error
import urllib.request

import segredos

ORDEM_PADRAO = "gemini,groq,openai,ollama"
MODELOS_PADRAO = {"gemini": "gemini-2.5-flash", "groq": "openai/gpt-oss-120b", "openai": "gpt-4o-mini",
                  "ollama": "llama3.2"}
GROQ_VISAO = "qwen/qwen3.8-27b"  # modelo do Groq que enxerga imagens (JARVIS_GROQ_VISAO no .env troca)
LIMITE_TEXTO = {"gemini": 400_000, "groq": 60_000, "openai": 200_000, "ollama": 20_000}  # caracteres

log = logging.getLogger("jarvis")


def _modelo(provedor):
    return segredos.obter(f"JARVIS_{provedor.upper()}_MODELO", MODELOS_PADRAO[provedor])


def configurados():
    """Provedores de reserva prontos para uso, na ordem escolhida."""
    ordem = [p.strip() for p in segredos.obter("JARVIS_IA_ORDEM", ORDEM_PADRAO).split(",") if p.strip()]
    chaves = {"gemini": "GEMINI_API_KEY", "groq": "GROQ_API_KEY", "openai": "OPENAI_API_KEY"}
    prontos = []
    for provedor in ordem:
        if provedor in chaves and segredos.obter(chaves[provedor]):
            prontos.append(provedor)
        elif provedor == "ollama" and _ollama_ligado():
            prontos.append(provedor)
    return prontos


def _ollama_url():
    return segredos.obter("JARVIS_OLLAMA_URL", "http://localhost:11434").rstrip("/")


def _ollama_ligado():
    try:
        with urllib.request.urlopen(_ollama_url() + "/api/tags", timeout=2):
            return True
    except (urllib.error.URLError, OSError):
        return False


def _post(url, corpo, cabecalhos, limite):
    # sem User-Agent o Groq (Cloudflare) recusa com "error code: 1010"
    pedido = urllib.request.Request(url, data=json.dumps(corpo).encode("utf-8"),
                                    headers={"Content-Type": "application/json", "User-Agent": "Jarvis/1.0",
                                             **cabecalhos})
    with urllib.request.urlopen(pedido, timeout=limite) as resposta:
        return json.loads(resposta.read().decode("utf-8"))


def _jpeg_pequeno(imagem_png, largura=1280):
    import io
    from PIL import Image
    imagem = Image.open(io.BytesIO(imagem_png)).convert("RGB")
    if imagem.width > largura:
        imagem = imagem.resize((largura, round(imagem.height * largura / imagem.width)))
    saida = io.BytesIO()
    imagem.save(saida, "JPEG", quality=75)
    return saida.getvalue()


def _chamar(provedor, sistema, texto, imagem_png=None, limite=120):
    texto = texto[:LIMITE_TEXTO[provedor]]
    modelo = _modelo(provedor)
    if provedor == "gemini":
        partes = [{"text": texto}]
        if imagem_png:
            partes.append({"inline_data": {"mime_type": "image/png", "data": base64.b64encode(imagem_png).decode()}})
        corpo = {"contents": [{"role": "user", "parts": partes}]}
        if sistema:
            corpo["system_instruction"] = {"parts": [{"text": sistema}]}
        dados = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent", corpo,
                      {"x-goog-api-key": segredos.obter("GEMINI_API_KEY")}, limite)
        return "".join(p.get("text", "") for p in dados["candidates"][0]["content"]["parts"]).strip()
    if provedor in ("groq", "openai"):
        conteudo = texto
        if imagem_png:
            tipo, dados_imagem = "image/png", imagem_png
            if provedor == "groq":  # o Groq aceita imagens pequenas: vai em JPEG, no máximo 1280 de largura
                modelo = segredos.obter("JARVIS_GROQ_VISAO", GROQ_VISAO)
                tipo, dados_imagem = "image/jpeg", _jpeg_pequeno(imagem_png)
            conteudo = [{"type": "text", "text": texto},
                        {"type": "image_url",
                         "image_url": {"url": f"data:{tipo};base64," + base64.b64encode(dados_imagem).decode()}}]
        mensagens = ([{"role": "system", "content": sistema}] if sistema else []) + [{"role": "user", "content": conteudo}]
        url = ("https://api.groq.com/openai/v1/chat/completions" if provedor == "groq"
               else "https://api.openai.com/v1/chat/completions")
        chave = segredos.obter("GROQ_API_KEY" if provedor == "groq" else "OPENAI_API_KEY")
        dados = _post(url, {"model": modelo, "messages": mensagens}, {"Authorization": f"Bearer {chave}"}, limite)
        return dados["choices"][0]["message"]["content"].strip()
    if provedor == "ollama":
        mensagens = ([{"role": "system", "content": sistema}] if sistema else []) + [{"role": "user", "content": texto}]
        dados = _post(_ollama_url() + "/api/chat", {"model": modelo, "messages": mensagens, "stream": False}, {}, limite * 3)
        return dados["message"]["content"].strip()
    raise ValueError(f"Provedor desconhecido: {provedor}")


def responder(texto, sistema="", imagem_png=None, limite=120):
    """Pergunta às IAs de reserva, uma de cada vez, até uma responder. Devolve (texto, provedor) ou (None, None).
    Com imagem, só as que enxergam imagens (Gemini, Groq pelo modelo de visão e OpenAI)."""
    for provedor in configurados():
        if imagem_png and provedor not in ("gemini", "groq", "openai"):
            continue
        try:
            resposta = _chamar(provedor, sistema, texto, imagem_png, limite)
            if resposta:
                log.info("IA de reserva respondeu: %s (%s)", provedor, _modelo(provedor))
                return resposta, provedor
        except (urllib.error.URLError, OSError, KeyError, IndexError, ValueError, TypeError) as erro:
            detalhe = erro.read().decode("utf-8", "replace")[:200] if isinstance(erro, urllib.error.HTTPError) else str(erro)
            log.warning("IA de reserva %s falhou: %s", provedor, detalhe)
    return None, None
