"""Engenharia reversa de estudo: entender COMO um APK ou site foi feito.

Faz análise estática e estrutural — lê o manifesto, as permissões, as bibliotecas e os arquivos — e pede ao
Claude para explicar a arquitetura e as técnicas. Serve para aprender e para apps/sites do próprio usuário.
Não quebra proteções, não remove licenças e não reconstrói conteúdo protegido por direitos autorais.
"""
import glob
import json
import logging
import os
import re
import subprocess
import zipfile

PASTA = os.path.dirname(os.path.abspath(__file__))
SDK = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Android", "Sdk")

log = logging.getLogger("jarvis")

# Assinaturas de arquivos que revelam com que tecnologia o app foi feito
PISTAS_FRAMEWORK = [
    ("lib/*/libflutter.so", "Flutter (Dart)"),
    ("assets/flutter_assets/*", "Flutter (Dart)"),
    ("assets/index.android.bundle", "React Native"),
    ("lib/*/libreactnativejni.so", "React Native"),
    ("lib/*/libhermes.so", "React Native (motor Hermes)"),
    ("assets/bin/Data/*", "Unity (jogo)"),
    ("lib/*/libunity.so", "Unity (jogo)"),
    ("lib/*/libil2cpp.so", "Unity IL2CPP"),
    ("lib/*/libmonodroid.so", ".NET MAUI / Xamarin"),
    ("assets/capacitor.config.json", "Capacitor (web dentro de app)"),
    ("assets/www/*", "Cordova/Capacitor (web dentro de app)"),
    ("assets/public/*", "Capacitor (web dentro de app)"),
    ("kotlin/*", "Kotlin nativo"),
]

INSTRUCOES_APK = (
    "Você é engenheiro de software ajudando o usuário a ENTENDER como um aplicativo Android foi construído, "
    "para fins de estudo. Recebe a análise estática de um APK (manifesto, permissões, bibliotecas e estrutura). "
    "Explique em português do Brasil, em texto claro: 1) com que tecnologia o app foi feito (Kotlin/Java nativo, "
    "Flutter, React Native, Unity etc.) e como você percebeu; 2) o que as permissões e serviços revelam sobre o "
    "que ele faz; 3) a provável arquitetura e as técnicas-chave para alcançar a função principal, no nível de "
    "conceito e de quais APIs do Android seriam usadas; 4) como alguém construiria um app parecido do zero, de forma "
    "original. Não forneça passos para quebrar proteção, remover anúncios/licenças, burlar pagamento ou piratear. "
    "Se o usuário parecer querer clonar um app de terceiros, lembre com uma linha que ele deve criar algo original e "
    "respeitar direitos autorais e marcas. Comece a resposta com um resumo de 2 frases que possa ser lido em voz alta."
)

INSTRUCOES_SITE = (
    "Você é engenheiro front-end ajudando o usuário a entender como um site foi construído, para estudo. "
    "Você pode buscar a página com WebFetch e olhar o HTML, o CSS e o JavaScript públicos (o mesmo que o 'ver código "
    "fonte' do navegador mostra). Explique em português do Brasil: a provável stack (framework, bibliotecas, "
    "hospedagem), a estrutura das telas, o estilo visual (cores, fontes, layout) e as técnicas interessantes. "
    "Depois diga como recriar algo parecido de forma original. Não copie textos nem código proprietário literalmente "
    "e não acesse áreas protegidas por login. Comece com um resumo de 2 frases para ser lido em voz alta."
)


def _aapt2():
    achados = sorted(glob.glob(os.path.join(SDK, "build-tools", "*", "aapt2.exe")))
    return achados[-1] if achados else None


def _badging(apk):
    """Manifesto legível do APK: pacote, versão, permissões, recursos, SDK alvo."""
    aapt2 = _aapt2()
    if not aapt2:
        return "(aapt2 não encontrado; pulei a leitura do manifesto)"
    try:
        saida = subprocess.run(
            [aapt2, "dump", "badging", apk],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW, timeout=120,
        )
        linhas = (saida.stdout or saida.stderr).splitlines()
        # tira as centenas de traduções do nome do app e de idiomas: não ajudam a entender o funcionamento
        uteis = [l for l in linhas if not re.match(r"(application-label-|locales:|densities:|application-icon-)", l)]
        return "\n".join(uteis[:300])
    except Exception as erro:
        return f"(falha ao ler o manifesto: {erro})"


def _estrutura(apk):
    """Lista o conteúdo do APK, detecta o framework e resume as pastas."""
    frameworks, pastas, total = set(), {}, 0
    with zipfile.ZipFile(apk) as pacote:
        nomes = pacote.namelist()
    for nome in nomes:
        topo = nome.split("/")[0]
        pastas[topo] = pastas.get(topo, 0) + 1
        total += 1
    import fnmatch
    for padrao, tecnologia in PISTAS_FRAMEWORK:
        if any(fnmatch.fnmatch(nome, padrao) for nome in nomes):
            frameworks.add(tecnologia)
    dex = sum(1 for nome in nomes if nome.endswith(".dex"))
    libs = sorted({nome.split("/")[-1] for nome in nomes if nome.startswith("lib/") and nome.endswith(".so")})
    partes = [
        f"Total de arquivos: {total}",
        f"Arquivos .dex (código compilado): {dex}",
        "Tecnologia detectada: " + (", ".join(sorted(frameworks)) if frameworks else "nenhuma pista clara (provável Kotlin/Java nativo)"),
        "Pastas principais: " + ", ".join(f"{p} ({n})" for p, n in sorted(pastas.items(), key=lambda x: -x[1])[:12]),
    ]
    if libs:
        partes.append("Bibliotecas nativas (.so): " + ", ".join(libs[:30]))
    return "\n".join(partes)


def relatorio_apk(apk):
    """Monta o texto de análise estática que vai para o Claude."""
    return (
        f"Arquivo: {os.path.basename(apk)}\n\n"
        f"=== MANIFESTO (aapt2 badging) ===\n{_badging(apk)}\n\n"
        f"=== ESTRUTURA DO PACOTE ===\n{_estrutura(apk)}"
    )


def analisar_apk(apk, ao_evento=None):
    """Analisa um APK e devolve (deu_certo, explicação). Usa o Claude só para explicar o texto já extraído."""
    import claude_code
    if not os.path.exists(apk):
        return False, "Não encontrei esse APK, senhor."
    log.info("Engenharia de APK: %s", apk)
    try:
        dados = relatorio_apk(apk)
    except zipfile.BadZipFile:
        return False, "Esse arquivo não é um APK válido, senhor."
    pedido = (
        "Explique como este aplicativo foi construído, a partir desta análise estática. "
        "Não preciso que você abra mais nada.\n\n" + dados[:60000]
    )
    # APK grande leva mais tempo para a análise: dá até 10 minutos
    return claude_code.analisar_material(pedido, INSTRUCOES_APK, ["Read"], limite=600)


def analisar_site(url, ao_evento=None):
    """Analisa como um site foi feito. O Claude busca a página pública e explica."""
    import claude_code
    log.info("Engenharia de site: %s", url)
    pedido = f"Analise como este site foi construído, buscando a página: {url}"
    return claude_code.analisar_material(pedido, INSTRUCOES_SITE, ["WebFetch", "WebSearch"])
