"""Seus comandos: a sua própria linguagem para o Jarvis, guardada em meus_comandos.json.

Cada comando tem frases de ativação e uma ação. As frases podem ter partes variáveis entre chaves, como
"pesquisa rápida {busca}": o que você falar no lugar de {busca} vai para dentro da ação.

Tipos de ação (fixos e seguros: não existe "executar comando de terminal"; programas abrem sem shell):
- responder:  o Jarvis fala um texto.
- abrir:      abre um site ou arquivo.
- pasta:      abre uma pasta.
- programa:   abre um programa.
- comandos:   uma sequência de frases que o Jarvis já entende ("abre o gmail na mini tela", "liga o modo foco"...).
- perguntar:  um prompt que o Claude responde em voz alta.
- mini_tela:  uma tarefa que o Jarvis faz sozinho no navegador da mini tela.

Dá para criar falando ("cria um comando: quando eu disser X, faça Y"): o Claude transforma o pedido num comando,
o Jarvis lê de volta e só salva se você confirmar. O arquivo é lido a cada comando: salvou, já vale.
"""
import json
import logging
import os
import re
import subprocess
import unicodedata
import webbrowser

PASTA = os.path.dirname(os.path.abspath(__file__))
ARQUIVO = os.path.join(PASTA, "meus_comandos.json")
TIPOS = {"responder", "abrir", "pasta", "programa", "comandos", "perguntar", "mini_tela"}
TIPOS_CRIADOS_POR_VOZ = {"responder", "abrir", "comandos", "perguntar", "mini_tela"}
MAX_PASSOS = 10

AJUDA = [
    "Seus comandos: a sua própria linguagem para o Jarvis. Salve o arquivo e fale: vale na hora, sem reiniciar.",
    "Mais fácil: diga 'Jarvis, cria um comando: quando eu disser X, faça Y' ou use o painel Meus comandos.",
    "Cada comando tem 'frases' (o que você fala) e 'acao'. Partes variáveis vão entre chaves: 'pesquisa rápida {busca}'.",
    "Tipos de acao:",
    "  {\"tipo\": \"responder\", \"texto\": \"...\"}                  -> ele fala esse texto",
    "  {\"tipo\": \"abrir\", \"alvo\": \"https://...\"}                -> abre um site ou arquivo",
    "  {\"tipo\": \"pasta\", \"caminho\": \"C:\\\\Users\\\\...\"}          -> abre uma pasta",
    "  {\"tipo\": \"programa\", \"caminho\": \"notepad\", \"args\": []}   -> abre um programa (sem terminal)",
    "  {\"tipo\": \"comandos\", \"lista\": [\"abre o gmail na mini tela\", \"liga o modo foco\"]} -> vários comandos em sequência",
    "  {\"tipo\": \"perguntar\", \"texto\": \"prompt para o Claude\"}  -> o Claude responde em voz",
    "  {\"tipo\": \"mini_tela\", \"tarefa\": \"...\"}                  -> o Jarvis faz a tarefa sozinho na mini tela",
]

EXEMPLOS_DE_FRASES = (
    "abre o youtube | abre o gmail na mini tela | abre g1.globo.com na mini tela | pesquisa no bing {x} | "
    "pesquisa {x} (no Google, no navegador) | toca {música} (YouTube dentro do Jarvis) | baixa o vídeo {x} | "
    "baixa a música {x} em mp3 | baixa todos os vídeos que tiver {x} | faz um relatório da playlist {link} | "
    "resume os vídeos sobre {x} | me lembra em 10 minutos de {x} | me lembra às 15:30 de {x} | timer de 5 minutos | "
    "liga o modo foco | modo foco por 1 hora a cada 20 minutos | desliga o modo foco | quais são meus lembretes | "
    "aumenta o volume | diminui o volume | silencia | próxima música | pausa | que horas são | que dia é hoje | "
    "status do sistema | abre a biblioteca | gera o pdf do projeto | abre o último app | cria um site de {x} | "
    "na mini tela, {tarefa com vários passos} | usa a tela e {tarefa no computador} | abre a calculadora | "
    "abre o bloco de notas | abre o spotify | conta uma piada"
)

INSTRUCOES_CRIAR = (
    "Você transforma o pedido do usuário num COMANDO PERSONALIZADO do BRAGA, o assistente de voz dele (Windows, "
    "português do Brasil). Responda SOMENTE com um JSON válido, sem texto antes ou depois:\n"
    '{"nome": "nome curto", "frases": ["frase de ativação"], "acao": {...}, '
    '"descricao": "uma frase curta em pt-BR, sem markdown, dizendo o que o comando faz (o Jarvis vai ler em voz alta)"}\n'
    "Regras das frases: minúsculas, sem a palavra jarvis, curtas e fáceis de falar. Se o usuário disse como quer "
    "chamar, use exatamente isso. Partes variáveis vão entre chaves, como 'pesquisa rápida {busca}', e o mesmo "
    "{busca} pode ser usado dentro da ação.\n"
    "Tipos de acao permitidos:\n"
    '- {"tipo": "responder", "texto": "..."}: o Jarvis fala um texto fixo.\n'
    '- {"tipo": "abrir", "alvo": "https://..."}: abre um site no navegador do Windows.\n'
    '- {"tipo": "comandos", "lista": ["...", "..."]}: sequência de até 10 frases que o Jarvis JÁ entende. '
    "Use as formas destes exemplos: " + EXEMPLOS_DE_FRASES + "\n"
    '- {"tipo": "perguntar", "texto": "prompt"}: o Claude responde em voz alta (resumos, ideias, explicações).\n'
    '- {"tipo": "mini_tela", "tarefa": "..."}: o Jarvis faz sozinho, no navegador da mini tela, uma tarefa de '
    "vários passos (pesquisar, abrir resultados, ler uma página).\n"
    "Prefira 'comandos' quando o pedido junta coisas que o Jarvis já sabe fazer. NUNCA crie comandos que enviem "
    "mensagens ou e-mails, publiquem, comprem, paguem, apaguem arquivos, desliguem o computador ou mexam no código "
    'do Jarvis; nesses casos responda {"erro": "motivo curto em pt-BR"}.'
)

# ações que uma sequência nunca dispara (risco de laço ou de mexer no próprio Jarvis)
ACOES_PROIBIDAS_NA_SEQUENCIA = {"autoatualizar", "comando_criar", "comando_apagar"}

log = logging.getLogger("jarvis")


def _normalizar(texto):
    sem = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in sem if unicodedata.category(c) != "Mn")


def _ler_arquivo():
    try:
        with open(ARQUIVO, encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
        return dados if isinstance(dados, dict) else {}
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError):
        log.warning("meus_comandos.json inválido", exc_info=True)
        return {}


def _carregar():
    return [c for c in _ler_arquivo().get("comandos", []) if isinstance(c, dict)]


def _gravar(comandos):
    dados = {"_ajuda": AJUDA, "comandos": comandos}
    temporario = ARQUIVO + ".tmp"
    with open(temporario, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2)
    os.replace(temporario, ARQUIVO)


# ---------- reconhecer ----------
def _casar(frase, texto, original=None):
    """Se a frase casa com o que foi falado, devolve as variáveis ({} se não tiver). Senão, None.

    Sem variáveis: casa se todas as palavras da frase aparecem no que foi falado (o jeito antigo).
    Com variáveis ("pesquisa rapida {busca}"): as partes fixas precisam vir em ordem, e o resto vira a variável.
    """
    if "{" not in frase and re.search(r"[/.\\]", frase):
        # código ("b/00000", "a/100/100/100/200"): só vale se for exatamente o código, sem contar espaços.
        # "a/0109010011 {pedido}" digitado com as chaves também cai aqui (e o Jarvis explica como usar)
        falado = re.sub(r"\{\w+\}", "", texto)
        return {} if re.sub(r"\s+", "", falado) == re.sub(r"\s+", "", _normalizar(frase)) else None
    if "{" not in frase:
        palavras = re.findall(r"\w+", _normalizar(frase))
        if palavras and all(re.search(rf"\b{re.escape(p)}\b", texto) for p in palavras):
            return {}
        return None
    partes = re.split(r"(\{\w+\})", _normalizar(frase))
    padrao = ""
    for parte in partes:
        if re.fullmatch(r"\{\w+\}", parte):
            padrao += rf"(?P<{parte[1:-1]}>.+?)"
        elif parte.strip():
            padrao += r"\s*" + r"\s+".join(re.escape(p) for p in parte.split()) + r"\s*"
    achado = re.fullmatch(rf"(?:pode\s+|por favor\s+)?{padrao}", texto.strip())
    if not achado or any(re.fullmatch(r"\{\w+\}", v.strip()) for v in achado.groupdict().values()):
        return None  # o modelo digitado com as chaves ("{pedido}") não é um pedido de verdade
    valores = {}
    for nome, valor in achado.groupdict().items():
        inicio, fim = achado.span(nome)
        # devolve com acentos, se o texto original tiver o mesmo tamanho
        valores[nome] = (original[inicio:fim] if original and len(original) == len(texto) else valor).strip()
    return valores


def _trocar(valor, variaveis):
    if isinstance(valor, str):
        return re.sub(r"\{(\w+)\}", lambda m: variaveis.get(_normalizar(m.group(1)), m.group(0)), valor)
    if isinstance(valor, list):
        return [_trocar(v, variaveis) for v in valor]
    return valor


def tentar(texto_normalizado, original=None):
    """Se algum comando seu casar, devolve a resposta (texto) ou uma ação para o Jarvis (dict). Senão, None."""
    for comando in _carregar():
        frases = comando.get("frases", [])
        for frase in frases:
            variaveis = _casar(frase, texto_normalizado, original)
            if variaveis is None:
                continue
            acao = {k: _trocar(v, variaveis) for k, v in (comando.get("acao") or {}).items()}
            try:
                return _executar_acao(acao, comando)
            except Exception:
                log.exception("Falha no comando do usuário %r", frases[:1])
                return "Não consegui executar esse comando, senhor. Veja o registro."
    return None


def _executar_acao(acao, comando):
    tipo = acao.get("tipo")
    if tipo == "responder":
        return acao.get("texto", "Feito, senhor.")
    if tipo == "abrir":
        alvo = acao.get("alvo", "")
        if alvo.startswith(("http://", "https://")):
            webbrowser.open(alvo)
        else:
            os.startfile(alvo)
        return "Abrindo, senhor."
    if tipo == "pasta":
        os.startfile(acao.get("caminho", PASTA))
        return "Abrindo a pasta, senhor."
    if tipo == "programa":
        import isolamento
        if isolamento.ligado():  # sites e pastas já vão para o notebook virtual; programa não abre no PC
            return isolamento.bloqueado(os.path.basename(str(acao.get("caminho", "esse programa"))))
        # sem shell: o caminho e os argumentos vão direto ao programa
        subprocess.Popen([acao.get("caminho")] + list(acao.get("args", [])),
                         creationflags=subprocess.CREATE_NO_WINDOW)
        return "Abrindo o programa, senhor."
    if tipo == "comandos":
        return {"acao": "sequencia", "frases": [f for f in acao.get("lista", []) if isinstance(f, str)][:MAX_PASSOS],
                "nome": comando.get("nome") or (comando.get("frases") or [""])[0]}
    if tipo == "perguntar":
        return {"acao": "perguntar", "texto": acao.get("texto", "")}
    if tipo == "mini_tela":
        return {"acao": "navegador_agente", "tarefa": acao.get("tarefa", "")}
    return f"Não conheço o tipo de ação '{tipo}' no seu arquivo, senhor."


# ---------- listar, criar e apagar ----------
def descrever(comando):
    acao = comando.get("acao") or {}
    tipo = acao.get("tipo")
    if comando.get("descricao"):
        return comando["descricao"]
    if tipo == "comandos":
        return "faz: " + "; ".join(acao.get("lista", []))
    return {"responder": f"responde: {acao.get('texto', '')}", "abrir": f"abre {acao.get('alvo', '')}",
            "pasta": f"abre a pasta {acao.get('caminho', '')}", "programa": f"abre {acao.get('caminho', '')}",
            "perguntar": f"pergunta ao Claude: {acao.get('texto', '')}",
            "mini_tela": f"na mini tela: {acao.get('tarefa', '')}"}.get(tipo, str(tipo))


def listar():
    return [{"nome": c.get("nome") or (c.get("frases") or ["?"])[0], "frases": c.get("frases", []),
             "descricao": descrever(c)} for c in _carregar()]


def validar(comando):
    """Confere um comando criado pelo Claude. Devolve (comando limpo, None) ou (None, motivo)."""
    if not isinstance(comando, dict):
        return None, "não entendi o comando"
    if comando.get("erro"):
        return None, str(comando["erro"])
    frases = [f.strip().lower() for f in comando.get("frases", []) if isinstance(f, str) and f.strip()]
    frases = [re.sub(r"^jarvis[,\s]+", "", f) for f in frases]
    acao = comando.get("acao")
    if not frases or not isinstance(acao, dict) or acao.get("tipo") not in TIPOS_CRIADOS_POR_VOZ:
        return None, "o comando veio incompleto"
    if acao["tipo"] == "abrir" and not str(acao.get("alvo", "")).startswith(("http://", "https://")):
        return None, "só consigo criar comandos que abrem sites"
    if acao["tipo"] == "comandos":
        lista = [f for f in acao.get("lista", []) if isinstance(f, str) and f.strip()][:MAX_PASSOS]
        if not lista:
            return None, "a sequência veio vazia"
        acao["lista"] = lista
    existentes = {_normalizar(f) for c in _carregar() for f in c.get("frases", [])}
    repetidas = [f for f in frases if _normalizar(f) in existentes]
    if repetidas:
        return None, f"já existe um comando com a frase '{repetidas[0]}'"
    limpo = {"nome": str(comando.get("nome") or frases[0])[:40], "frases": frases, "acao": acao,
             "descricao": str(comando.get("descricao") or "")[:200]}
    return limpo, None


def criar_do_prompt(prompt):
    """O Claude transforma o pedido falado num comando. Devolve (comando, None) ou (None, motivo)."""
    import claude_code
    if not claude_code.disponivel():
        return None, "o Claude Code não está instalado"
    deu_certo, resposta = claude_code.resumir(f"Pedido do usuário: {prompt}", INSTRUCOES_CRIAR, limite=120)
    if not deu_certo:
        return None, "o Claude não respondeu agora"
    inicio, fim = resposta.find("{"), resposta.rfind("}")
    try:
        comando = json.loads(resposta[inicio:fim + 1]) if inicio >= 0 else None
    except json.JSONDecodeError:
        comando = None
    return validar(comando)


def salvar(comando):
    comandos = _carregar()
    comandos.append(comando)
    _gravar(comandos)
    log.info("Comando criado: %s", comando.get("frases"))


def buscar(termo):
    termo = _normalizar(termo).strip()
    if not termo:
        return []
    return [c for c in _carregar()
            if termo in _normalizar(c.get("nome", "")) or any(termo in _normalizar(f) for f in c.get("frases", []))]


def remover(comando):
    comandos = [c for c in _carregar() if c != comando]
    _gravar(comandos)
    log.info("Comando apagado: %s", comando.get("frases"))
