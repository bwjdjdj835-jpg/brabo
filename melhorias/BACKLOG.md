# Backlog de melhorias do Jarvis

Trabalho feito em ciclos pelo Claude (/loop). Cada ciclo: um item, testado, commitado no git local.
Para desfazer um ciclo: `git log` e `git revert <commit>`.

Regra: tudo que publica, instala, clica na tela ou apaga pede confirmação ("Confirma?") antes.

## A fazer
- [ ] 3. Voz mais Jarvis: efeito de rádio/metálico leve, escolher voz, interromper a fala ("para")
- [ ] 6. Publicar o último site/web app na Vercel (com confirmação; precisa `npx vercel login` uma vez)
- [ ] 7. Instalar programas pelo winget ("instala o VLC"), com confirmação
- [ ] 8. Criar apps mais rápido (modelo, modelos de projeto prontos, menos espera)
- [ ] 9. Ideias da pesquisa "como fazer um Jarvis" (lembretes, timer, clima, rotina...)

## Feito
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
- [x] 4+5. Ver a tela e clicar: já existia (agente_tela.py, "usa a tela e ..."; pânico = mouse no canto superior esquerdo)
- [x] Já existiam: bot do Telegram, comandos personalizados (meus_comandos.json), segredos no .env
