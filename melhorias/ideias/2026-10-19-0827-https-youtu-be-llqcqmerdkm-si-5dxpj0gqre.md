# Ideias dos vídeos: https://youtu.be/lLQCqMErDkM?si=5dxpJ0gqRea3d9r2

Gerado pelo Jarvis em 19/10/2026 08:27.

## Vídeos
- [Instale o JARVIS no seu PC (100% grátis) | assistente de IA que fala, ouve e agenda](https://www.youtube.com/watch?v=lLQCqMErDkM)

## O que os vídeos ensinam

**Instale o JARVIS no seu PC (100% grátis)**: O autor instala do zero um assistente open source (projeto jgm-source/jarvis-opensource no GitHub). Os passos são: clonar o projeto, instalar Python (com "Add to PATH") e rodar um comando de setup no prompt. Depois ele cadastra as chaves: Gemini (gratuita, Google AI Studio), Groq (para ouvir, grátis) e Fish Audio (voz clonada do Jarvis do Tony Stark, exige adicionar pelo menos US$ 5 no developer e, segundo ele, fica grátis até dezembro). Ele separa as funções: Groq ouve, Gemini pensa e responde, Fish fala. Também menciona DeepSeek como opção barata, mas que soa robótica.

O assistente tem uma tela de "Plugin Settings" para as chaves, um painel com CPU e memória, avatares trocáveis (três modos), log de erros e atalho na área de trabalho. Na inicialização ele fala uma saudação, toca a música do Tony Stark e resume novidades: um canal do YouTube que o autor acompanha, o sistema de rastreamento dele e a agenda do dia. Também há um "modo foco" que lembra de beber água.

Nas opções, dá para cadastrar até três chaves do Gemini com troca automática quando uma acaba, escolher a voz, e fazer o Jarvis responder só quando ouvir a palavra "Jarvis", continuando a escutar depois de fazer uma pergunta. Na demo, ele consulta o sistema real do autor por API: clientes esperando suporte há dias, vendas e faturamento do dia (inclusive da Cakto). O autor diz que ele também abre navegador, faz pesquisas e abre programas do PC. A ideia central: qualquer sistema com API aberta, webhook ou planilha (Google Sheets) pode ser integrado, e a IA de código (Codex, Open Code) é usada para editar o projeto.

## Ideias para o Jarvis

1. **Palavra de ativação ("Jarvis") com conversa contínua**: o assistente só reage quando ouve o nome e, depois de fazer uma pergunta, continua escutando a resposta por alguns segundos. Como fazer: no loop do SpeechRecognition, checar se a transcrição contém "jarvis" e manter uma janela de escuta (ex.: 10 s) após cada pergunta dele. Dá para filtrar localmente sem gastar API.

2. **Rodízio automático de várias chaves de API**: o vídeo guarda até três chaves do Gemini e troca quando uma estoura a cota. Como fazer: lista de chaves no `.env`/config e um `try/except` que captura erro 429 ou de cota e passa para a próxima. (precisa de chave)

3. **Separar ouvir, pensar e falar em provedores diferentes**: usar um serviço gratuito para transcrição e outro para a resposta, economizando tokens. Como fazer: Groq (API de Whisper, biblioteca `groq`) para ouvir; manter o `edge-tts` (grátis) para falar. (precisa de chave, no caso do Groq; o vídeo diz que o plano é gratuito)

4. **Briefing de abertura personalizado**: ao iniciar, o Jarvis diz bom dia, resume a agenda do dia, novidades de um canal do YouTube e dados do negócio. Como fazer: no startup, juntar dados (RSS do canal do YouTube via `feedparser`, agenda via Google Calendar API) e pedir ao Claude para resumir em duas frases. (precisa de chave, para o Google Calendar)

5. **Integração com sistemas por API/webhook/planilha**: perguntas do tipo "quantas vendas hoje?" ou "tem cliente esperando suporte?". Como fazer: criar plugins em Python com `requests` para as APIs dos sistemas que o usuário usa, ou ler Google Sheets com `gspread`. Cada plugin vira um comando de voz. (precisa de chave, conforme o sistema)

6. **Tela de configurações de plugins/chaves**: uma aba na interface (pywebview) para colar as chaves e testar a conexão, mostrando "conectada". Como fazer: formulário no HTML que chama métodos da `js_api` do pywebview e grava num arquivo local fora do git, com botão "testar" que faz uma chamada simples à API.

7. **Painel de status do sistema**: mostrar CPU, memória e uso do PC na interface. Como fazer: biblioteca `psutil`, atualizando a cada poucos segundos no pywebview.

8. **Voz mais marcante, tipo Jarvis do filme**: o vídeo usa Fish Audio com voz clonada. Como fazer: API do Fish Audio (SDK `fish-audio-sdk`) com o ID da voz escolhida, mantendo o `edge-tts` como reserva se a chave falhar. (precisa de chave; o vídeo diz que exige depósito mínimo de US$ 5)

9. **Música e saudação de abertura configuráveis**: tocar um tema ao iniciar e variar a fala (por exemplo, com o nome do usuário). Como fazer: `pygame.mixer` ou `playsound` para o áudio, e um campo de texto na configuração para a saudação.

10. **Lembretes de bem-estar e "modo foco"**: avisos periódicos, como beber água, durante um período de foco. Como fazer: `threading.Timer` ou `schedule` disparando uma fala, ativado por comando de voz.

11. **Trocar o avatar/visual da interface**: oferecer vários modos de animação do círculo que reage à fala. Como fazer: alternar CSS/Canvas no pywebview e guardar a escolha na configuração.

12. **Log de erros visível na interface**: uma aba que mostra os erros recentes, para copiar e colar numa IA que corrige. Como fazer: módulo `logging` com um handler que envia as linhas para o pywebview via `window.evaluate_js`.
