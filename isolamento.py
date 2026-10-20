"""Como o Braga abre sites, arquivos, pastas e programas.

Padrão (modo isolado DESLIGADO): o mini notebook é o PC de verdade. Antes de abrir qualquer coisa no PC, o Braga
mostra o mini notebook e fica por cima de tudo (ao_abrir_no_pc); a janela nova nasce ATRÁS do Braga e o senhor vê
e mexe nela pelo mini notebook. Fechando o Braga, está tudo lá no notebook de verdade.

Modo isolado (só se o senhor pedir): tudo o que o Braga faria aparecer no PC aparece só dentro do Braga, no
notebook virtual (o navegador invisível do Braga, mostrado na tela do notebook 3D).

- Sites (webbrowser.open): abrem no notebook virtual, não no Edge/Chrome do Windows.
- Arquivos e pastas (os.startfile, Explorador): abrem no notebook virtual como file:/// (vídeo, PDF, site, foto e
  texto o navegador mostra; pasta vira a lista de arquivos).
- Programas do Windows, Bloco de Notas, Android Studio, atalho na área de trabalho e o "PC real" (mouse e
  teclado de verdade): bloqueados enquanto o modo isolado estiver ligado.
Os comandos de terminal que o Braga roda por dentro (Claude Code, gh, yt-dlp) já são escondidos (sem janela).

Ligar: "liga o modo isolado"; desligar: "desliga o modo isolado" (com confirmação). O estado fica em
isolamento.json.
"""
import json
import logging
import os
import urllib.parse
import webbrowser

PASTA = os.path.dirname(os.path.abspath(__file__))
ARQUIVO = os.path.join(PASTA, "isolamento.json")
MOSTRAVEIS = (".html", ".htm", ".pdf", ".mp4", ".webm", ".mp3", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg",
              ".txt", ".md", ".json", ".csv", ".log", ".env", ".py", ".js", ".css")

log = logging.getLogger("jarvis")
ao_abrir = None        # o app põe aqui a função que mostra um endereço no notebook virtual
ao_bloquear = None     # a que avisa o senhor quando algo foi bloqueado
ao_abrir_no_pc = None  # e a que abre o mini notebook (Braga por cima) antes de algo abrir no PC de verdade


def antes_de_abrir_no_pc():
    """Chamar logo antes de abrir uma janela no PC: ela nasce atrás do Braga, dentro do mini notebook."""
    if ao_abrir_no_pc:
        try:
            ao_abrir_no_pc()
        except Exception:
            log.debug("Não consegui preparar o mini notebook antes de abrir", exc_info=True)
_originais = {}


def ligado():
    try:
        with open(ARQUIVO, encoding="utf-8") as arquivo:
            return bool(json.load(arquivo).get("ligado", False))
    except (OSError, ValueError):
        return False  # sem arquivo: o mini notebook é o PC de verdade (o que abre fica atrás do Braga)


def ligar(sim=True):
    with open(ARQUIVO, "w", encoding="utf-8") as arquivo:
        json.dump({"ligado": bool(sim)}, arquivo)
    log.info("Modo isolado %s", "ligado" if sim else "desligado")


def endereco_de(alvo):
    """Site -> ele mesmo; arquivo ou pasta -> file:///...; programa -> None (não dá para abrir no virtual)."""
    alvo = str(alvo or "").strip()
    if alvo.startswith(("http://", "https://", "file:///")):
        return alvo
    caminho = os.path.abspath(os.path.expandvars(alvo)) if alvo else ""
    if caminho and (os.path.isdir(caminho) or (os.path.isfile(caminho) and caminho.lower().endswith(MOSTRAVEIS))):
        return "file:///" + urllib.parse.quote(caminho.replace("\\", "/"), safe="/:")
    return None


def bloqueado(o_que, verbo="abro"):
    """Registra e avisa que algo foi bloqueado. Devolve a frase para o Braga falar."""
    frase = (f"Modo isolado ligado, senhor: não {verbo} {o_que} no seu PC. Para isso, diga: desliga o modo isolado.")
    log.info("Modo isolado bloqueou: %s", o_que)
    if ao_bloquear:
        ao_bloquear(frase)
    return frase


def abrir(alvo):
    """Abre um site, arquivo ou pasta no notebook virtual (isolado) ou no Windows (desligado). True se abriu."""
    if not ligado():
        antes_de_abrir_no_pc()
        if str(alvo).startswith(("http://", "https://")):
            return _originais.get("webbrowser", webbrowser.open)(alvo)
        _originais.get("startfile", os.startfile)(alvo)
        return True
    endereco = endereco_de(alvo)
    if not endereco:
        bloqueado(os.path.basename(str(alvo)) or str(alvo))
        return False
    if ao_abrir:
        ao_abrir(endereco)
    else:
        import navegador
        navegador.abrir(endereco)
    return True


def instalar():
    """Troca o webbrowser.open e o os.startfile do processo pelo abrir() isolado: qualquer parte do Braga (e os
    comandos que o senhor criou) passa por aqui, mesmo as que não sabem do modo isolado."""
    if _originais:
        return
    _originais["webbrowser"] = webbrowser.open
    _originais["startfile"] = os.startfile

    def abrir_site(url, *args, **kwargs):
        return abrir(url)

    def abrir_arquivo(caminho, *args, **kwargs):
        if not ligado():
            antes_de_abrir_no_pc()
            return _originais["startfile"](caminho, *args, **kwargs)
        abrir(caminho)

    webbrowser.open = webbrowser.open_new = webbrowser.open_new_tab = abrir_site
    os.startfile = abrir_arquivo
