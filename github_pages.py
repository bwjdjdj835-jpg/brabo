"""Publica um site (uma pasta com index.html) no GitHub Pages, com o GitHub CLI (gh) do usuário.

Precisa, uma vez só: instalar o gh (winget install GitHub.cli) e entrar na conta com `gh auth login`.
O Jarvis nunca vê a senha: o login fica com o próprio gh. Publicar deixa o site PÚBLICO na internet, então
quem chama precisa ter a confirmação do usuário antes.
"""
import logging
import os
import shutil
import subprocess

log = logging.getLogger("jarvis")
LUGARES_DO_GH = [r"C:\Program Files\GitHub CLI\gh.exe", r"C:\Program Files (x86)\GitHub CLI\gh.exe",
                 os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "GitHub CLI", "gh.exe")]


def _gh():
    return shutil.which("gh") or next((c for c in LUGARES_DO_GH if os.path.exists(c)), None)


def _rodar(comando, pasta=None, limite=120):
    resultado = subprocess.run(comando, cwd=pasta, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=limite, creationflags=subprocess.CREATE_NO_WINDOW)
    return resultado.returncode, (resultado.stdout or "").strip(), (resultado.stderr or "").strip()


def situacao():
    """(pronto, frase). pronto=False explica o que falta: instalar o gh ou fazer login."""
    gh = _gh()
    if not gh:
        return False, ("O programa do GitHub não está instalado. Instale com: winget install GitHub.cli, "
                       "e depois entre na sua conta com: gh auth login.")
    codigo, _, _ = _rodar([gh, "auth", "status"], limite=30)
    if codigo:
        return False, "O GitHub está instalado, mas falta entrar na sua conta: abra o terminal e digite gh auth login."
    return True, "GitHub pronto."


def usuario():
    codigo, saida, erro = _rodar([_gh(), "api", "user", "--jq", ".login"], limite=30)
    if codigo or not saida:
        raise RuntimeError(f"Não consegui saber o seu usuário do GitHub: {erro[:150]}")
    return saida


def publicar(pasta_site, nome_repo, descricao=""):
    """Cria o repositório público, envia o site e liga o GitHub Pages. Devolve o endereço do site."""
    gh = _gh()
    login = usuario()
    git = ["git", "-c", f"user.name={login}", "-c", f"user.email={login}@users.noreply.github.com"]
    if not os.path.isdir(os.path.join(pasta_site, ".git")):
        _rodar(["git", "init", "-q"], pasta_site)
    _rodar(git + ["add", "-A"], pasta_site)
    _rodar(git + ["commit", "-q", "-m", "Prévia do site"], pasta_site)
    _rodar(["git", "branch", "-M", "main"], pasta_site)
    codigo, _, erro = _rodar([gh, "repo", "view", f"{login}/{nome_repo}"], limite=30)
    if codigo:  # ainda não existe: cria e envia
        codigo, _, erro = _rodar([gh, "repo", "create", nome_repo, "--public", "--source", pasta_site,
                                  "--remote", "origin", "--push", "--description", descricao[:300]], pasta_site, 180)
        if codigo:
            raise RuntimeError(f"O GitHub não criou o repositório {nome_repo}: {erro[:200]}")
    else:  # já existe (publicado antes): só atualiza
        _rodar(["git", "remote", "add", "origin", f"https://github.com/{login}/{nome_repo}.git"], pasta_site)
        codigo, _, erro = _rodar(["git", "push", "-u", "origin", "main", "--force"], pasta_site, 180)
        if codigo:
            raise RuntimeError(f"Não consegui enviar o site para {nome_repo}: {erro[:200]}")
    codigo, _, erro = _rodar([gh, "api", "-X", "POST", f"repos/{login}/{nome_repo}/pages",
                              "-f", "source[branch]=main", "-f", "source[path]=/"], limite=60)
    if codigo and "already" not in erro.lower() and "409" not in erro:
        log.warning("GitHub Pages de %s: %s", nome_repo, erro[:200])
    endereco = f"https://{login}.github.io/{nome_repo}/"
    log.info("Publicado no GitHub Pages: %s", endereco)
    return endereco
