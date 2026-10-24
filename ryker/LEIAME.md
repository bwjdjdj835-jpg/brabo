# RYKER: a camada real do agente visual

O RYKER é o Braga trabalhando sozinho no PC enquanto o Ryker aparece no quarto 3D (`interface/ryker`).
Documento de arquitetura completo: https://claude.ai/artifact/2qsCLydzFrGFNSrEoBSLwN

## Pastas

| Pasta | Faz | Hoje |
|---|---|---|
| `core/` | Barramento de eventos (`eventos.py`) | Pronto, testado |
| `vision/` | Captura da tela (`captura.py`: mss ou dxcam) | Pronto para medir; o mini notebook ainda usa o próprio mss |
| `desktop/` | Mini notebook (`notebook.py`): tela real ao vivo, controle, sessão | Movido de `notebook.py` |
| `ocr/` | Leitura de texto (`leitor.py`: Windows OCR ou RapidOCR) | Pronto para medir |
| `automation/` | Mouse, teclado e foto para a IA (`tela.py`) | Movido de `tela.py` |
| `memory/` | Conversa e tarefas (`memoria.py`) | Movido de `memoria.py` |
| `planner/` | Objetivo -> plano | Fase 3 |
| `agent/` | Agente de tela (`agente_tela.py`) | Movido de `agente_tela.py` |
| `room/`, `camera/` | O quarto e as câmeras ficam em `interface/ryker` (Three.js) | Ligações do Python na Fase 5 |
| `ui/` | Voz, chat e confirmações (hoje no `app.py`) | Aos poucos |

Os arquivos antigos na raiz (`tela.py`, `notebook.py`, `agente_tela.py`, `memoria.py`) ficaram só como atalho:
`import notebook` continua funcionando e devolve o MESMO módulo de `ryker/desktop/notebook.py` (mesmo estado).

## Medições da Fase 1 (24/10/2026, este notebook: i5-13420H, 7,7 GB, Intel UHD, tela 1920x1200)

Rodar de novo: `python tools/medir_fase1.py` (resultado bruto em `ryker/medicoes_fase1.json`).
O Braga estava aberto durante a medição e o PC tinha pouca memória livre, então os números de memória são aproximados.

### Captura da tela

| | MSS | DXcam |
|---|---|---|
| Tempo por foto | 84 ms | 24 ms |
| Processador a 10 fotos/s | 3,5% do PC | 3,2% do PC |
| Memória a mais | ~32 MB | ~64 MB |

**Escolha:** DXcam para o espelho e para o "observar" do agente (3,5x mais rápido, mesmo gasto de processador),
com o MSS de reserva automática. Antes de trocar no mini notebook (Fase 2): conferir que a janela do Braga continua
fora da captura com o DXcam (sem efeito túnel).

### OCR (texto de interface em pt-BR, Segoe UI 12/14/18 px, fundo claro e escuro)

| | Windows OCR | RapidOCR |
|---|---|---|
| Palavras certas, com acento | **96%** | 56% |
| Palavras certas, ignorando acento | 99% | 78% |
| Tempo (imagem de teste) | 0,24 s | 5,6 s |
| Tempo (tela inteira) | 0,65 s | 12,5 s |
| Tempo (um quarto da tela, "janela ativa") | 0,16 s | 5,2 s |
| Primeira leitura | 0,5 s | 13,6 s |
| Idiomas | pt-BR e pt-PT já instalados | modelo chinês/inglês: perde os acentos |

**Escolha:** Windows OCR. O RapidOCR foi 20x mais lento e errou quase metade das palavras com acento; sai do plano.
Ler só a janela ativa (0,16 s) em vez da tela toda (0,65 s).
