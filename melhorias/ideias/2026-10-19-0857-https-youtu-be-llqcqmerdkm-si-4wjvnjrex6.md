# Ideias dos vídeos: https://youtu.be/lLQCqMErDkM?si=4wjVNJreX6RlzL8z

Gerado pelo Jarvis em 19/10/2026 08:57.

## Vídeos
- [Instale o JARVIS no seu PC (100% grátis) | assistente de IA que fala, ouve e agenda](https://www.youtube.com/watch?v=lLQCqMErDkM)

## O que os vídeos ensinam

**Vídeo 1: Instale o JARVIS no seu PC (100% grátis)**
O autor instala do zero um Jarvis open source (projeto `jgm-source/jarvis-opensource` no GitHub). Ele usa Python, uma chave gratuita do Gemini (Google AI Studio), Groq para ouvir (transcrição), Gemini ou DeepSeek como cérebro e Fish Audio para a voz estilo Tony Stark. Ele separa "ouvir" e "falar" em serviços diferentes para gastar menos token.

A interface tem painel de plugins e configurações, três avatares animados e um monitor de CPU e memória. Também tem logs de erro, que dá para mandar a uma IA para corrigir. Na partida, ele fala uma saudação, resume novidades de um canal do YouTube, mostra a agenda e toca música de abertura.

No fim, ele integra o Jarvis ao próprio sistema de vendas por API. O Jarvis responde quantas vendas foram feitas no dia e se há cliente esperando no suporte. O autor diz que ele também abre navegador, faz pesquisa e abre programas do PC.

## Ideias para o Jarvis

1. **Ativação só pela palavra "Jarvis" (wake word), com conversa contínua depois.** O vídeo cita isso como forma de deixar o microfone aberto sem gastar token. Como fazer: no loop do SpeechRecognition, só enviar à IA quando a frase começar com "jarvis". Depois, manter uma janela de escuta de alguns segundos para a resposta. Para detecção offline, a `pvporcupine` (Picovoice) funciona, mas precisa de chave (precisa de chave).

2. **Separar "ouvir" de "falar" para economizar.** O vídeo usa Groq só para transcrever e outra IA para responder. Como fazer: a API do Groq com Whisper (`groq` no pip, modelo `whisper-large-v3`) tem camada gratuita, e você manda o áudio gravado pelo microfone (precisa de chave).

3. **Rodízio de várias chaves do Gemini.** Quando uma chave bate o limite, o Jarvis troca para a próxima. Como fazer: guardar uma lista de chaves no `.env`, capturar o erro 429 ou de cota no `google-genai` e tentar a seguinte (precisa de chave).

4. **Integrações com dados reais por API, webhook ou planilha.** Os exemplos do vídeo são vendas do dia e clientes sem resposta. Como fazer: criar "ferramentas" no Jarvis, que são funções Python chamando `requests` nas APIs dos seus sistemas ou lendo o Google Sheets com `gspread`. A IA decide qual função chamar (function calling). Cada integração pode precisar de chave do serviço (precisa de chave).

5. **Saudação de abertura personalizada (briefing).** Ao iniciar, o Jarvis fala bom dia, mostra a agenda e resume novidades. Como fazer: no startup, juntar a agenda (Google Calendar API), notícias ou um canal do YouTube (RSS do canal, sem chave, com `feedparser`) e gerar um resumo falado. A agenda do Google exige credenciais OAuth (precisa de chave).

6. **Modo foco com lembretes.** O vídeo mostra o Jarvis avisando para beber água no "modo foco". Como fazer: usar `threading.Timer` ou `APScheduler` para lembretes periódicos, acionados por um comando de voz.

7. **Voz mais natural e personalizável.** O vídeo usa o Fish Audio, que permite clonar uma voz ou escolher entre muitas. O autor diz que o plano de API exige recarga mínima de R$ 5, e que uma promoção de áudio gratuito vai só até dezembro. Como fazer: chamar a API do Fish Audio no lugar do edge-tts, mantendo o edge-tts como alternativa gratuita (precisa de chave).

8. **Escolha de voz e humor nas configurações.** Dá para trocar entre vozes e mudar a personalidade do Jarvis. Como fazer: guardar no JSON de configurações a voz do edge-tts e um texto de personalidade, colocado no prompt de sistema.

9. **Painel de status do sistema.** Mostrar CPU e memória na interface, como no vídeo. Como fazer: `psutil.cpu_percent()` e `psutil.virtual_memory()`, enviados para a interface do pywebview por JavaScript.

10. **Tela de logs com atalho para pedir correção.** O autor copia erros da tela de logs e manda para uma IA corrigir. Como fazer: mostrar o log na interface e criar um botão que envia o trecho ao Claude Code para propor a correção.

11. **Abrir navegador e programas por voz.** Já é o caminho que o vídeo mostra. Como fazer: `webbrowser.open` e `os.startfile`, e para achar programas instalados, procurar no Menu Iniciar (`.lnk`) ou usar `pywinauto`.

12. **Avatares alternativos.** O vídeo mostra três modos de visual que animam quando ele fala. Como fazer: no front-end do pywebview, animar um canvas ou SVG conforme o volume do áudio (Web Audio API).

Observação: o vídeo não explica o código interno do projeto, só a instalação e o uso. Se quiser aproveitar mais, dá para ler o repositório do GitHub citado na descrição.
