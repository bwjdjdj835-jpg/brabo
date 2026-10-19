# Ideias dos vídeos: https://youtu.be/lLQCqMErDkM?si=4wjVNJreX6RlzL8z

Gerado pelo Jarvis em 19/10/2026 09:00.

## Vídeos
- [Instale o JARVIS no seu PC (100% grátis) | assistente de IA que fala, ouve e agenda](https://www.youtube.com/watch?v=lLQCqMErDkM)

## O que os vídeos ensinam

**Vídeo 1: Instale o JARVIS no seu PC (100% grátis)**
O autor instala do zero um assistente open source (projeto jgm-source/jarvis-opensource) que fala, ouve e agenda. O passo a passo é: clonar do GitHub, instalar o Python marcando "Add to PATH", rodar o setup e colocar as chaves de API.

A arquitetura divide as tarefas para sair de graça ou barato:
- **Groq** para ouvir (transcrição).
- **Gemini** (chave gratuita do Google AI Studio) como cérebro, que também pode falar.
- **DeepSeek** como alternativa barata, mas com fala mais robótica.
- **Fish Audio** para a voz do Jarvis, com voz clonável ou escolhida no catálogo. Exige depósito mínimo de R$ 5 na conta de desenvolvedor, e o autor diz que o modelo S2.1 fica de graça até dezembro.

Na interface há várias opções:
- **Rodízio de chaves:** até 3 chaves do Gemini, trocando quando uma acaba.
- **Palavra de ativação:** responde só quando ouve "Jarvis" e continua ouvindo depois de fazer uma pergunta.
- **Avatares:** 3 modos de avatar.
- **Painel de uso:** CPU e memória.
- **Registro de erros:** o autor manda o erro para uma IA corrigir.

Ao iniciar, o Jarvis fala uma saudação, as novidades de um canal do YouTube que o autor acompanha, atualizações do sistema dele e a agenda do dia, tocando uma música de abertura. Ele também lembra de beber água em "modo foco".

Na demo, o autor ligou o Jarvis às APIs do próprio sistema e perguntou por voz quantos clientes foram rastreados no dia e se havia cliente esperando no suporte. Ele diz que dá para integrar qualquer coisa com API aberta, webhook ou planilha (Google Sheets, Cacto etc.). O Jarvis também abre o navegador, pesquisa e abre programas do PC.

## Ideias para o Jarvis

1. **Rodízio de várias chaves do Gemini (precisa de chave)**
   Guarde uma lista de chaves gratuitas no `.env`. Ao receber erro 429 ou de cota, troque para a próxima chave no cliente `google-genai`. Assim o Jarvis quase nunca para por limite.

2. **Separar "ouvir" de "pensar" usando o Groq para transcrição (precisa de chave)**
   Troque ou complemente o SpeechRecognition pelo endpoint de áudio do Groq, que é compatível com a API da OpenAI e usa Whisper. Chave gratuita em console.groq.com. A transcrição tende a ficar mais precisa que a do reconhecedor padrão, e o Gemini gasta token só para responder.

3. **Palavra de ativação "Jarvis" com conversa de continuação**
   Mantenha o microfone aberto e só processe a frase quando ela contiver "jarvis". Depois de uma pergunta do Jarvis, escute por alguns segundos sem exigir a palavra. Dá para fazer só com a lógica de texto sobre o que o SpeechRecognition já devolve, sem biblioteca nova.

4. **Resumo falado ao iniciar (briefing de abertura)**
   Ao abrir, o Jarvis diz bom dia e lê as novidades dos canais do YouTube que o usuário acompanha, mais a agenda do dia. Use o RSS dos canais (`youtube.com/feeds/videos.xml?channel_id=...`) com `feedparser`, e o Google Calendar via API do Google (OAuth, sem custo). A API do Google já está em uso no Drive, então dá para reaproveitar o login.

5. **Rodízio entre vozes e opção de voz mais natural: Fish Audio (precisa de chave)**
   Adicione o Fish Audio como motor de voz opcional, mantendo o edge-tts como padrão gratuito e de reserva. Basta uma chave de API e o ID da voz escolhida no catálogo. Lembre que exige depósito mínimo de R$ 5 e que a promoção citada no vídeo vai até dezembro.

6. **Integrar com APIs, webhooks e planilhas do usuário**
   Crie um "plugin" simples por serviço (arquivo Python com uma função e uma descrição) que o Jarvis chama quando a pergunta combinar. Comece com Google Sheets via `gspread` ou a API do Google, para o usuário perguntar números por voz. O vídeo cita Sheets, webhooks e APIs de vendas, mas cada uma depende do serviço que o usuário usa e de uma chave dele (precisa de chave).

7. **Painel de configurações com chaves e testes**
   Uma tela em que o usuário cola cada chave (Gemini, Groq, Fish) e clica em "testar". Isso já cabe no pywebview. Guarde as chaves fora do git, em `.env` ou no Gerenciador de Credenciais do Windows via `keyring`.

8. **Lembretes de rotina e "modo foco"**
   Aviso falado periódico, como beber água, e um modo foco com temporizador. Use `threading.Timer` ou `schedule`, sem custo e sem chave.

9. **Status do sistema por voz**
   Responder "como está o PC?" com CPU, memória e disco usando `psutil`. É simples e grátis.

10. **Registro de erros visível, pronto para mandar ao Claude Code**
    Uma aba de log no pywebview com botão "copiar erro". O vídeo sugere mandar o erro para uma IA corrigir, e o Jarvis já tem o Claude Code como braço de programação. Para fazer: `logging` com arquivo rotativo e leitura desse arquivo na interface.

11. **Avatares e animação ao falar**
    O vídeo mostra 3 modos de avatar, com o círculo animado enquanto o Jarvis fala. Dá para fazer em CSS/JS dentro do pywebview, ligando a animação ao início e fim da fala. É só visual, mas dá personalidade.

12. **Música de abertura estilo filme**
    Tocar um trecho curto ao iniciar com `pygame.mixer` ou `playsound`. O usuário precisa fornecer o áudio, por causa de direitos autorais.

13. **LLM barato como alternativa: DeepSeek (precisa de chave)**
    O vídeo cita o DeepSeek como API muito barata, paga por recarga, mas com fala meio robótica. Como reserva quando as chaves gratuitas do Gemini acabarem, usa-se o cliente `openai` apontando para a URL do DeepSeek.
