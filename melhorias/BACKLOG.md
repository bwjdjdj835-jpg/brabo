# Backlog de melhorias do Jarvis

Trabalho feito em ciclos pelo Claude (/loop). Cada ciclo: um item, testado, commitado no git local.
Para desfazer um ciclo: `git log` e `git revert <commit>`.

Regra: tudo que publica, instala, clica na tela ou apaga pede confirmação ("Confirma?") antes.

## A fazer
- [ ] Código A/1070809.7080: publicar na Vercel (com confirmação), gravar prévias de campanha automotiva e preparar
  os vídeos para postagem (postar sempre com confirmação). Hoje o código só abre a Vercel na mini tela.
- [ ] Código C/01070910111213141516: renomear o assistente para "Braga"? (perguntar ao usuário: nome falado,
  palavra de chamada e título da janela)
- [ ] 3. Voz mais Jarvis: efeito de rádio/metálico leve, escolher voz, interromper a fala ("para")
- [ ] 6. Publicar o último site/web app na Vercel (com confirmação; precisa `npx vercel login` uma vez)
- [ ] 7. Instalar programas pelo winget ("instala o VLC"), com confirmação
- [ ] 8. Criar apps mais rápido (modelo, modelos de projeto prontos, menos espera)
- [ ] 9. Ideias da pesquisa "como fazer um Jarvis" (lembretes, timer, clima, rotina...)

## Feito
- [x] Fábrica de sites, código B/07070707 (fabrica_sites.py): negócios sem site no Maps -> print -> fotos do
  negócio (galeria do Maps) -> domínio livre (RDAP) -> modelo de design -> site completo feito pelo Claude Code
  com checagem automática em loop (até 3 voltas; sem Claude, IA de reserva; sem nenhuma, modelo pronto) -> print
  do site -> vídeo MP4 (Vídeos\Jarvis\Sites) -> zip -> mensagem -> GitHub Pages com confirmação (github_pages.py,
  precisa de `gh auth login` uma vez). "publica os sites no github" publica a última leva.
- [x] IAs de reserva (ia.py): Gemini, Groq, OpenAI e Ollama, chaves no .env (JARVIS_IA_ORDEM). Entram quando o
  Claude falha em conversa, resumos, ver a tela e no site da fábrica.
- [x] 0. PDF: juntar até 100 arquivos em um PDF (botão PDF, "gera o PDF do projeto")
- [x] 1. YouTube: "baixa o vídeo X" / "baixa a música X em mp3" / link → Vídeos\Jarvis (youtube.py, até 1080p, limite 3h)
- [x] 2. Abas: "toca X" toca o YouTube numa aba dentro do Jarvis ("no navegador" = jeito antigo), "abre o último app"
  abre o site numa aba, "fecha a aba" / "fecha todas as abas". Interface agora é servida por servidor.py (só 127.0.0.1,
  só interface/, projetos/ e pdfs/). A conferir pelo usuário: o vídeo tocando dentro da aba.
- [x] YouTube em lote: "baixa todos os vídeos que tiver jarvis" (só os que têm a busca no título, padrão 20, máx 50),
  "baixa 5 músicas do X", link de playlist (até 200). Pasta Vídeos\Jarvis\<busca ou playlist>.
- [x] Autoestudo (autoestudo.py): "resume os vídeos sobre como fazer um jarvis" lê as legendas (até 10 vídeos),
  o Claude resume e salva as ideias em melhorias/ideias/. "Jarvis, se atualiza" (com confirmação): backup no git,
  Claude Code muda o código, compila e importa o app; se quebrar, desfaz sozinho. Depois oferece reiniciar.
- [x] Relatório do YouTube em PDF (relatorio_youtube.py): botão PDF no painel ou "faz um relatório da playlist <link>".
  Todos os vídeos (até 200) com dados e descrição; os 10 primeiros com legenda lida; o Claude faz resumo geral,
  pontos principais e resumo por vídeo. Salva em pdfs/ e copia para Meu Drive\Jarvis\Relatórios do YouTube
  (google_drive.py acha a pasta do Google Drive para computador sozinho).
- [x] Ideias do vídeo "Instale o JARVIS no seu PC" (ideias/2026-10-19-0900-...):
  conversa de continuação (quando o Jarvis termina a fala com pergunta, como "Confirma?", a resposta vem sem dizer
  "Jarvis"); lembretes e timer ("me lembra em 10 minutos de tirar o bolo", "me lembra às 3 da tarde de...",
  "me acorda às 7", "timer de 5 minutos", "quais são meus lembretes", "cancela os lembretes"; ficam só na memória,
  somem se reiniciar); modo foco ("liga o modo foco", "modo foco por 1 hora a cada 20 minutos": lembra de beber água,
  "desliga o modo foco").
- [x] Ideias do vídeo "Instale o JARVIS no seu PC" (ideias/2026-10-19-0931-...):
  notícias ("quais as notícias", "notícias de futebol"; Google Notícias por RSS, sem chave, noticias.py);
  briefing do dia ("faz o briefing", "como está meu dia": data, hora, lembretes, status do PC e 3 manchetes);
  erros do registro ("quais foram os últimos erros", "o que deu errado": diagnostico.py lê o jarvis.log, mostra no
  painel e pergunta se pede ao Claude para corrigir, só com confirmação e com backup/desfazer da autoatualização);
  abrir qualquer programa instalado ("abre o google chrome"): se não está na lista, procura nos atalhos do Menu Iniciar.
- [x] Mini tela (navegador.py): Edge invisível controlado pelo Playwright, mostrado ao vivo numa aba da interface
  (imagem pelo servidor local com token). Dá para clicar, rolar, digitar e usar ← → ⟳ e endereço. Voz: "abre o g1
  na mini tela", "pesquisa X aqui", "na mini tela, pesquisa X e abre o primeiro resultado" (agente_tela com
  alvo=navegador, mesmos freios), "fecha a mini tela". Logins ficam em navegador_perfil/.
- [x] Sua linguagem de comandos (comandos_usuario.py + painel Meus comandos): "cria um comando: quando eu disser X,
  faça Y" -> o Claude transforma em comando (sequência de frases, prompt para o Claude, tarefa na mini tela,
  responder, abrir site), o Jarvis lê de volta e só salva com "sim". Variáveis: "pesquisa rápida {busca}".
  "quais são meus comandos", "apaga o comando X" (com confirmação). Recusa comandos que enviam, compram, apagam.
- [x] Atalho "Jarvis" na Área de Trabalho e no Menu Iniciar (jarvis.ico); se a janela não abrir em 60 s, reabre sozinho.
- [x] 4+5. Ver a tela e clicar: já existia (agente_tela.py, "usa a tela e ..."; pânico = mouse no canto superior esquerdo)
- [x] Já existiam: bot do Telegram, comandos personalizados (meus_comandos.json), segredos no .env

## Ideias dos vídeos (o Claude lê daqui para atualizar o Jarvis)
- [x] ideias/2026-10-19-0931-https-youtu-be-llqcqmerdkm-si-mo46wn-1ym.md (feito: ideias 2, 10 e 11; painel já existia) (https://youtu.be/lLQCqMErDkM?si=Mo46wn_1ymc-chkJ)
- [x] ideias/2026-10-19-0900-https-youtu-be-llqcqmerdkm-si-4wjvnjrex6.md (feito: ideias 3 e 8; status do PC já existia) (https://youtu.be/lLQCqMErDkM?si=4wjVNJreX6RlzL8z)
- [ ] ideias/2026-10-19-0857-https-youtu-be-llqcqmerdkm-si-4wjvnjrex6.md (https://youtu.be/lLQCqMErDkM?si=4wjVNJreX6RlzL8z)
- [ ] ideias/2026-10-19-0827-https-youtu-be-llqcqmerdkm-si-5dxpj0gqre.md (https://youtu.be/lLQCqMErDkM?si=5dxpJ0gqRea3d9r2)
