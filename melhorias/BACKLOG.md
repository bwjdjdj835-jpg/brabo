# Backlog de melhorias do Jarvis

Trabalho feito em ciclos pelo Claude (/loop). Cada ciclo: um item, testado, commitado no git local.
Para desfazer um ciclo: `git log` e `git revert <commit>`.

Regra: tudo que publica, instala, clica na tela ou apaga pede confirmação ("Confirma?") antes.

## A fazer
- [ ] 1. Baixar vídeo do YouTube por voz (yt-dlp): link ou nome do vídeo → pasta Vídeos\Jarvis
- [ ] 2. Abas na interface: YouTube (tocar dentro do Jarvis), sites e projetos abrindo em abas
- [ ] 3. Voz mais Jarvis: efeito de rádio/metálico leve, escolher voz, interromper a fala ("para")
- [ ] 4. Ver a tela: "o que tem na minha tela?" → print + Claude descreve
- [ ] 5. Clicar na tela por pedido ("clica em X"), sempre com confirmação
- [ ] 6. Publicar o último site/web app na Vercel (com confirmação; precisa `npx vercel login` uma vez)
- [ ] 7. Instalar programas pelo winget ("instala o VLC"), com confirmação
- [ ] 8. Criar apps mais rápido (modelo, modelos de projeto prontos, menos espera)
- [ ] 9. Ideias da pesquisa "como fazer um Jarvis" (lembretes, timer, clima, rotina...)

## Feito
- [x] 0. PDF: juntar até 100 arquivos em um PDF (botão PDF, "gera o PDF do projeto")
