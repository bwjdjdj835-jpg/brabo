# Ideias dos vídeos: https://youtu.be/vTIq4pUR7o0?is=lhE3OGDGJ7r80nnV

Gerado pelo Jarvis em 20/10/2026 10:46.

## Vídeos
- [Como construi o JARVIS do Homem de Ferro no N8N (TEMPLATE GRATUITO)](https://www.youtube.com/watch?v=vTIq4pUR7o0)

## O que os vídeos ensinam

**Como construí o JARVIS do Homem de Ferro no N8N (vídeo 1).** O autor monta um assistente pessoal em que o "Jarvis" só analisa o pedido e decide quais agentes especialistas acionar: um, dois ou todos ao mesmo tempo. Cada agente é um fluxo separado no N8N.
- **E-mail:** usa o Gmail, para enviar e-mail, marcar como prioridade e salvar rascunho.
- **Calendário:** cria, altera e apaga eventos.
- **Contatos:** consulta, adiciona e atualiza contatos numa base no Airtable.
- **Conteúdo:** usa a ferramenta de busca Tavily para pesquisar e escrever, por exemplo, um post de blog.

A voz e a personalidade ficam no ElevenLabs, num agente criado do zero:
- **Prompt:** um assistente inspirado no Jarvis, com humor afiado e sarcasmo sutil. O prompt foi gerado pelo ChatGPT.
- **Modelo:** GPT-5 com esforço de raciocínio no mínimo, para responder rápido, e temperatura alta (70 a 100%) para a personalidade ficar solta.
- **Voz:** clonada a partir de trechos do filme gravados com o celular. O ElevenLabs pede só cerca de 10 segundos de áudio. O autor usou o modelo "Flash" por causa da velocidade.
- **Ligação com o N8N:** uma ferramenta webhook do tipo POST recebe o pedido do usuário num campo `query`. O tempo máximo de resposta é de 120 segundos, e a duração da conversa foi aumentada para 1000 segundos.

A interface foi feita no Cursor, é responsiva e liga o microfone pelo botão ou pela tecla espaço. O efeito de holograma não saiu bem em código, então o autor achou outro jeito, que as legendas não detalham. O widget do ElevenLabs foi escondido. O vídeo termina com o download dos templates, mas as legendas acabam antes disso.

## Ideias para o Jarvis

1. **Orquestrador com agentes especialistas (e-mail, agenda, contatos, conteúdo).** Faça o Jarvis classificar o pedido e chamar uma função por área, usando tool use da API do Claude ou o Claude Code como roteador. Isso copia o desenho central do vídeo. (precisa de chave)
2. **Agente de agenda no Google Calendar.** Use `google-api-python-client` com OAuth para criar, mover e apagar eventos por voz e convidar participantes. Como no vídeo, o Jarvis deve repetir o horário final ("amanhã das 15h às 16h") antes de concluir. (precisa de chave: credenciais OAuth do Google Cloud)
3. **Agente de e-mail no Gmail.** Use a Gmail API para enviar, buscar o último e-mail de uma pessoa, marcar como importante e criar rascunho. O Jarvis já envia mensagens com confirmação, então vale manter o mesmo cuidado aqui. (precisa de chave: OAuth do Google)
4. **Perguntar o que falta antes de agir.** No vídeo, o agente pergunta tema, público, tom e tamanho antes de escrever o post, e oferece o próximo passo (lembrete, cobrar resposta). Isso se faz no prompt de sistema: "se faltar informação essencial, pergunte antes". Não depende de biblioteca nem de conta.
5. **Personalidade configurável (sarcasmo sutil, humor).** Coloque no prompt de sistema o tom do vídeo: sarcasmo leve, ironia bem-humorada, respostas curtas. Use temperatura alta nas respostas de conversa e baixa nas de ação. Não precisa de nada além do que o Jarvis já tem.
6. **Busca na web para criar conteúdo (Tavily).** Use o pacote `tavily-python`, ou outra API de busca, para o agente de conteúdo pesquisar e escrever um post ou resumo. (precisa de chave)
7. **Contatos consultáveis por voz.** O vídeo usa o Airtable. No Jarvis, dá para começar com o `contatos.csv` ou um SQLite local, com funções de buscar, adicionar e atualizar contato. Airtable via `pyairtable` seria a versão em nuvem. (Airtable precisa de chave; a versão local não)
8. **Voz clonada estilo filme.** Use o SDK `elevenlabs` com o modelo Flash, que o autor escolheu para ter baixa latência. Mantenha o edge-tts como reserva quando a chave faltar ou a cota acabar. (precisa de chave)
9. **Resposta rápida em vez de raciocínio longo.** O autor deixou o esforço de raciocínio no mínimo porque o modelo demorava a responder. No Jarvis, use um modelo leve ou pouco raciocínio nos pedidos de conversa e deixe o modelo forte para tarefas pesadas. (precisa de chave, se usar API paga)
10. **Tarefas longas em segundo plano.** O ElevenLabs corta a espera em 120 segundos e o agente responde "deu erro". O Jarvis pode evitar isso rodando a tarefa em uma thread, avisando por voz "estou nisso" e falando o resultado quando terminar. Isso se faz com `threading` ou `asyncio`, sem custo.
11. **Tecla espaço para ligar e desligar o microfone.** Capture o `keydown` do espaço na tela pywebview, ou use a biblioteca `keyboard` para um atalho global, e alterne o microfone do SpeechRecognition. Não depende de conta.

O vídeo não detalha o final da configuração do widget nem a parte do download dos templates, porque a legenda foi cortada. Também não diz nada sobre preço do ElevenLabs, do Tavily ou do Cursor, além de o autor ter pago pelo Cursor.
