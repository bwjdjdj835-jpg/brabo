# Ideias dos vídeos: https://youtu.be/lLQCqMErDkM?si=Mo46wn_1ymc-chkJ

Gerado pelo Jarvis em 19/10/2026 09:31.

## Vídeos
- [Instale o JARVIS no seu PC (100% grátis) | assistente de IA que fala, ouve e agenda](https://www.youtube.com/watch?v=lLQCqMErDkM)

## O que os vídeos ensinam

**Vídeo 1: Instale o JARVIS no seu PC (100% grátis)**
O autor instala do zero no Windows um assistente de voz de código aberto (jgm-source/jarvis-opensource). Os passos são: clonar o projeto do GitHub, instalar o Python e rodar um comando de setup que cria um atalho na área de trabalho. Depois ele cadastra as chaves de API na tela "Plugin Settings".

Para ser quase grátis, ele divide as funções entre serviços:
- **Gemini** (chave gratuita do Google AI Studio) faz o raciocínio e as respostas.
- **Groq** transcreve a sua fala, de graça.
- **Fish Audio** faz a voz do Jarvis (a do Tony Stark, escolhida na biblioteca de vozes). Exige depositar no mínimo R$ 5 para gerar a chave de API. O autor diz que um modelo (S2.1) fica sem custo até dezembro, e depois volta a ser pago.
- **DeepSeek** é uma opção barata para raciocínio, mas o autor achou a fala "robótica".

O vídeo também mostra:
- Ao iniciar, o Jarvis toca a música tema e fala um briefing: notícias, novidades de um canal do YouTube, dados do sistema de rastreamento do autor e a agenda do dia.
- O **modo foco** o lembra de beber água.
- Opções de economia: até três chaves do Gemini, que ele alterna quando uma acaba. Também dá para fazer o Jarvis responder só quando ouvir a palavra "Jarvis" e continuar ouvindo depois de fazer uma pergunta.
- O painel mostra CPU e memória, tem três modos de avatar e um log de erros que dá para mandar para uma IA corrigir.
- O Jarvis abre o navegador, faz pesquisas e abre programas do PC.
- Na demonstração real, ele consulta o suporte (cliente sem resposta há 10 dias) e o faturamento do dia. O autor diz que dá para integrar com qualquer API aberta, webhook ou planilha (Google Sheets), e que basta pedir a uma IA para criar a integração.

## Ideias para o Jarvis

1. **Reconhecimento de voz pelo Groq (precisa de chave).** O vídeo usa o Groq para ouvir de graça. No seu Jarvis, grave o áudio do microfone e envie para a API de transcrição do Groq (modelo Whisper) com o SDK `groq` ou `requests`. Deve reconhecer melhor que o `SpeechRecognition` com Google. Mantenha o atual como plano B se a chave falhar.

2. **Briefing falado ao iniciar.** Ao abrir, o Jarvis cumprimenta e resume o dia: agenda (Google Calendar API, precisa de chave/OAuth), novidades de um canal do YouTube que você acompanha (feed RSS do canal, sem chave, lido com `feedparser`) e uso do PC (`psutil`).

3. **Painel de saúde do PC.** Mostre CPU, memória e disco no painel do pywebview com `psutil`, atualizando a cada poucos segundos. O vídeo mostra isso e o Jarvis já fala sobre o sistema.

4. **Rodízio de várias chaves de API (precisa de chave).** Guarde uma lista de chaves e troque para a próxima quando a atual der erro de cota (HTTP 429). O vídeo faz isso com até três chaves do Gemini.

5. **Integração com planilhas e APIs do seu negócio (precisa de chave).** Para perguntas como "quanto faturei hoje?", puxe os dados do Google Sheets (`gspread` ou a API do Sheets) ou de qualquer API ou webhook com `requests`. Cada integração vira um comando que o Jarvis sabe chamar. Cadastre as chaves em uma tela de configurações, como o "Plugin Settings" do vídeo.

6. **Palavra de ativação com conversa contínua.** Deixe o microfone sempre ligado, mas só aja quando ouvir "Jarvis". Se o Jarvis fez uma pergunta, ele continua ouvindo por alguns segundos para a resposta, sem exigir a palavra de novo. Você já tem a resposta sem dizer "Jarvis"; falta só esse tempo de escuta após uma pergunta dele.

7. **Voz mais realista com Fish Audio (precisa de chave).** Hoje você usa `edge-tts`. O Fish Audio permite escolher ou clonar uma voz, e a chave exige depósito mínimo de R$ 5. Use a API de texto-para-fala dele e deixe o `edge-tts` como reserva quando o crédito acabar.

8. **Tela de configurações para chaves e preferências.** Uma página no pywebview onde você cola as chaves, escolhe a voz, liga ou desliga a palavra de ativação e testa a conexão com um botão. Salve num arquivo de configuração fora do git.

9. **Música tema e avatar personalizável.** Toque um áudio curto na inicialização (`pygame.mixer` ou `playsound`) e deixe trocar entre alguns estilos de avatar animado no painel, que se anima quando o Jarvis fala.

10. **Log de erros em tela, com botão para consertar.** Mostre os erros do Jarvis no painel e inclua um botão "mandar para o Claude Code corrigir", que envia o trecho do log como pedido. Combina com a autoatualização que você já tem.

11. **Abrir programas e sites por voz.** Abra programas do PC e faça pesquisas no navegador por comando, com `os.startfile`, `subprocess` e `webbrowser`. Se você já tem isso, vale revisar a lista de apps que ele reconhece.
