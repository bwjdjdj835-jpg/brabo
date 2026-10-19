"""Google Drive pelo programa "Google Drive para computador": ele mostra o Drive como uma pasta do Windows
("G:\\Meu Drive", por exemplo) e sobe sozinho o que for salvo lá. Assim o Jarvis não precisa de senha nem de
chave de API: é só copiar o arquivo para essa pasta.
"""
import logging
import os
import shutil
import string

SUBPASTA = "Jarvis"
NOMES = ("Meu Drive", "My Drive", "Mi unidad")

log = logging.getLogger("jarvis")


def pasta():
    """Pasta "Meu Drive" do usuário, ou None se o Google Drive para computador não estiver ligado e logado."""
    candidatos = [f"{letra}:\\{nome}" for letra in "G" + string.ascii_uppercase.replace("G", "") for nome in NOMES]
    candidatos += [os.path.join(os.path.expanduser("~"), nome) for nome in NOMES + ("Google Drive",)]
    for candidato in candidatos:
        if os.path.isdir(candidato):
            return candidato
    return None


def salvar(arquivo, subpasta=SUBPASTA):
    """Copia o arquivo para Meu Drive\\Jarvis\\<subpasta>. Devolve o caminho no Drive, ou None sem Drive."""
    raiz = pasta()
    if not raiz:
        return None
    destino = os.path.join(raiz, subpasta) if subpasta else raiz
    os.makedirs(destino, exist_ok=True)
    caminho = os.path.join(destino, os.path.basename(arquivo))
    shutil.copy2(arquivo, caminho)
    log.info("Enviado ao Google Drive: %s", caminho)
    return caminho
