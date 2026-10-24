// HUD do Quarto do Braga: liga a cena 3D do Ryker ao Braga (app.py) pela ponte do pywebview (pywebview.api).
// - A tela do ThinkPad 3D = a tela do PC ao vivo (quadros do mini notebook do Braga).
// - O que o Braga faz no PC (agente_tela) e o que o senhor faz aparece no Ryker: mão no touchpad, cliques, digitação.
// - Cliques na tela 3D só vão para o PC com o botão grande LIGADO. PARAR, Esc×3 e Ctrl+Alt+Q param tudo.
const $ = id => document.getElementById(id);
const api = () => window.pywebview && window.pywebview.api;

// a cena chega depois (precisa baixar o three.js); até lá, e se falhar, o resto do HUD funciona igual
let cena = { estado: {}, vista() {}, animarAcao: async () => {}, fimAcao() {}, evento() {}, aoClicarTela() {}, quadro: b => b.close && b.close(), aviso() {} };
import('./scene.js').then(m => {
  cena = m.criarCena($('cena'), erro => {
    if (erro) $('carregando').textContent = 'Não consegui carregar o quarto 3D. O resto do Braga funciona normal.';
    else $('carregando').hidden = true;
  });
  cena.aoClicarTela(cliqueNaTela);
}).catch(e => {
  $('carregando').textContent = 'Sem o 3D (precisa de internet para o three.js). O resto do Braga funciona normal.';
  try { api().erro_js('Quarto 3D: ' + e.message); } catch (_) {}
});

// ---------- conversa ----------
const chat = $('chat'), onda = $('onda');
for (let i = 0; i < 28; i++) onda.appendChild(document.createElement('i'));
setInterval(() => { $('relogio').textContent = new Date().toLocaleTimeString('pt-BR'); }, 500);

function addMsg(quem, texto) {
  const d = document.createElement('div'); d.className = 'msg' + (quem === 'eu' ? ' eu' : '');
  d.innerHTML = `<em>${quem === 'eu' ? 'VOCÊ' : 'BRAGA'}</em>`; d.append(texto);
  chat.appendChild(d); while (chat.children.length > 80) chat.firstChild.remove();
  chat.scrollTop = chat.scrollHeight;
}
let toastAte = 0;
function toast(texto, ms = 4000) {
  const t = $('toast'); t.textContent = texto; t.hidden = false; toastAte = Date.now() + ms;
  setTimeout(() => { if (Date.now() >= toastAte) t.hidden = true; }, ms + 50);
}

$('form').addEventListener('submit', ev => {
  ev.preventDefault();
  const texto = $('entrada').value.trim(); if (!texto) return;
  $('entrada').value = '';
  try { api().comando_texto(texto); } catch (_) { addMsg('braga', 'Falha de conexão com o núcleo do Braga.'); }
});

// ---------- fala: a voz do Braga (edge-tts) tocada aqui, com a boca do Ryker no volume da voz ----------
let ctx = null, analisador = null, dados = null, falando = false, medindo = false;
function audioCtx() {
  if (!ctx) {
    ctx = new AudioContext(); analisador = ctx.createAnalyser(); analisador.fftSize = 512;
    dados = new Uint8Array(analisador.fftSize); analisador.connect(ctx.destination);
  }
  return ctx;
}
async function tocar(b64) {
  const audio = new Audio('data:audio/mpeg;base64,' + b64);
  let terminou = false;
  const fim = () => {
    if (terminou) return;
    terminou = true; falando = false; medindo = false;
    try { api().fim_fala(); } catch (_) {}
  };
  audio.onended = fim; audio.onerror = fim;
  try {
    const c = audioCtx();
    if (c.state !== 'running') await Promise.race([c.resume(), new Promise(r => setTimeout(r, 300))]).catch(() => {});
    if (c.state === 'running') { c.createMediaElementSource(audio).connect(analisador); medindo = true; }
  } catch (_) { medindo = false; }
  falando = true;
  try { await audio.play(); } catch (_) { fim(); }
}
function bip() {
  try {
    const c = audioCtx(), osc = c.createOscillator(), ganho = c.createGain();
    osc.frequency.setValueAtTime(880, c.currentTime); osc.frequency.linearRampToValueAtTime(1320, c.currentTime + .12);
    ganho.gain.setValueAtTime(.15, c.currentTime); ganho.gain.exponentialRampToValueAtTime(.001, c.currentTime + .18);
    osc.connect(ganho).connect(c.destination); osc.start(); osc.stop(c.currentTime + .2);
  } catch (_) {}
}
(function anima() {
  let alvo = 0;
  if (falando && medindo) {
    analisador.getByteTimeDomainData(dados);
    let soma = 0; for (const v of dados) soma += (v - 128) * (v - 128);
    alvo = Math.min(1, Math.sqrt(soma / dados.length) / 40);
  } else if (falando) alvo = .3 + Math.random() * .5;
  const e = cena.estado; e.falando = falando; e.nivel = (e.nivel || 0) + (alvo - (e.nivel || 0)) * .35;
  document.body.classList.toggle('falando', falando);
  onda.querySelectorAll('i').forEach((b, i) => {
    b.style.height = (falando ? 6 + e.nivel * 40 * Math.abs(Math.sin(i * .7 + performance.now() / 120)) : 4 + Math.sin(i + performance.now() / 400) * 2) + 'px';
  });
  requestAnimationFrame(anima);
})();

// ---------- funções chamadas pelo Python (jarvis._ui) ----------
const NOMES_ESTADO = { ouvindo: 'PRONTO PARA OUVIR', escutando: 'ESCUTANDO', pensando: 'PENSANDO', falando: 'FALANDO',
  pausado: 'MICROFONE PAUSADO', 'sem-microfone': 'SEM MICROFONE', offline: 'OFFLINE' };
let trabalhando = false;
const funcoes = {
  estado(s) {
    $('estado').textContent = NOMES_ESTADO[s] || String(s).toUpperCase();
    document.body.dataset.estado = s;
    if (s === 'escutando') $('legenda').textContent = 'Pode falar, estou ouvindo…';
    else if (s === 'pensando') $('legenda').textContent = 'Um momento, senhor…';
  },
  voceDisse(t) { addMsg('eu', t); },
  ouviu(t) { $('legenda').textContent = 'ouvi: ' + t; },
  falaTexto(t) { addMsg('braga', t); $('legenda').textContent = t; },
  tocarAudio(b64) { tocar(b64); },
  micEstado(ligado) { micEstado(ligado); },
  bip() { bip(); },
  aviso(t) { addMsg('braga', t); toast(t); },
  nota(t) { addMsg('braga', t); },
  comandoProposto(frases, descricao) { addMsg('braga', `Comando novo: "${(frases || []).join('" / "')}" — ${descricao || ''}`); },
  atividade(t) { $('tarefa-passo').textContent = t; if (trabalhando) $('legenda').textContent = t; },
  tarefa(titulo, pedido) {
    trabalhando = !!titulo;
    $('tarefa').hidden = !trabalhando;
    $('tarefa-titulo').textContent = trabalhando ? `${titulo}${pedido ? ': ' + pedido : ''}` : '';
    $('tarefa-passo').textContent = '';
    if (!trabalhando) { fonte = 'pc'; numeroQuadro = ''; }
  },
  abrirNotebook(f) { fonte = f || 'pc'; numeroQuadro = ''; navInfo = null; trocarVista('ombro'); },
  abrirAba(titulo, url) { $('aba-titulo').textContent = titulo || ''; $('aba-frame').src = url; $('aba').hidden = false; },
  fecharAba() { $('aba').hidden = true; $('aba-frame').src = 'about:blank'; },
  abrirNavegador() { toast('Abrindo a mini tela no painel completo…'); setTimeout(() => { location.href = '../index.html?abrir=navegador'; }, 400); },
  parado(motivo) { cena.fimAcao(); mostrarControle(false); toast('PARADO: ' + (motivo || 'emergência')); },
};
// o Braga chama várias funções do painel completo (biblioteca, skills...): aqui elas só são ignoradas
window.jarvis = new Proxy(funcoes, { get: (alvo, nome) => alvo[nome] || (() => {}) });

// ---------- vistas da câmera ----------
const NOMES_VISTA = { live5d: 'LIVE · câmera 5D no tripé', medio: 'Medium shot', close: 'Close-up na tela', ombro: 'Por cima do ombro', tela: 'Tela de frente', live: 'Frente (mesa)', orbita: '360° órbita', quarto: 'Quarto', rosto: 'Close no rosto' };
function trocarVista(v) {
  document.querySelectorAll('.vistas button').forEach(x => x.classList.toggle('on', x.dataset.v === v));
  cena.vista(v); $('vistaNome').textContent = NOMES_VISTA[v];
}
document.querySelectorAll('.vistas button').forEach(b => b.onclick = () => trocarVista(b.dataset.v));

// ---------- tela do PC ao vivo na tela do ThinkPad ----------
let nbInfo = null, navInfo = null, fonte = 'pc', numeroQuadro = '', buscando = false;
const doNavegador = () => fonte === 'navegador' && trabalhando;   // tarefa no notebook virtual (navegador do Braga)
async function buscarQuadro() {
  if (buscando || document.hidden || !api() || !api().notebook_info) return;
  buscando = true;
  try {
    if (!nbInfo) nbInfo = await api().notebook_info();
    const info = doNavegador() ? (navInfo || (navInfo = await api().navegador_info())) : nbInfo;
    const r = await fetch(`${info.quadro}?n=${numeroQuadro}&t=${Date.now()}`, { cache: 'no-store' });
    if (r.ok) {
      numeroQuadro = r.headers.get('X-Quadro') || '';
      if (r.status === 200) cena.quadro(await createImageBitmap(await r.blob()));
    } else cena.aviso('Captura da tela indisponível agora');
  } catch (_) {}
  buscando = false;
}

// ---------- o que está acontecendo no PC: cursor, registro de ações, Braga trabalhando ----------
let acoesVistas = '', cursorAntes = null;
async function lerEstado() {
  if (document.hidden || !api() || !api().notebook_estado) return;
  let s; try { s = await api().notebook_estado(); } catch (_) { return; }
  const e = cena.estado;
  if (s.cursor && !e.acao && !doNavegador()) {
    if (cursorAntes && Math.abs(s.cursor[0] - cursorAntes[0]) + Math.abs(s.cursor[1] - cursorAntes[1]) > .004) cena.evento('mouse');
    e.cursor = cursorAntes = s.cursor;
  }
  e.agente = !!s.controlando;
  document.body.classList.toggle('agente', e.agente);
  $('pausar').hidden = !!s.pausado; $('retomar').hidden = !s.pausado;
  const acoes = s.acoes || [];
  const marca = acoes.length ? acoes[0].hora + acoes[0].texto : '';
  if (marca && marca !== acoesVistas) {
    for (const a of acoes) {
      if (a.hora + a.texto === acoesVistas) break;
      if (/^(Digitou|Tecla|Senhor digitou|Senhor: tecla)/.test(a.texto)) cena.evento('digitar');
      else if (/^(Clique|Senhor: (clicar|duplo|direito|tocar))/.test(a.texto)) cena.evento('clicar');
      else if (/^Rolou/.test(a.texto)) cena.evento('rolar');
    }
    acoesVistas = marca;
    $('log').innerHTML = '';
    for (const a of acoes.slice(0, 14)) {
      const d = document.createElement('div');
      if (/Parad|freio|Falha|erro/i.test(a.texto)) d.className = 'erro';
      d.innerHTML = `<b>${a.hora}</b> `; d.append(a.texto);
      $('log').append(d);
    }
  }
}

// ---------- cliques do senhor na tela 3D = cliques no PC (só LIGADO) ----------
let controleLigado = false;
function mostrarControle(v) {
  controleLigado = v; cena.estado.controle = v;
  const b = $('togControle'); b.classList.toggle('on', v); b.classList.toggle('off', !v);
  $('togTxt').textContent = v ? 'CLIQUES NA TELA: LIGADOS' : 'CLIQUES NA TELA: DESLIGADOS';
  document.body.classList.toggle('controlando', v);
}
$('togControle').onclick = () => {
  const quer = !controleLigado;
  if (quer && !confirm('Ligar os cliques? Clicar na tela do notebook 3D vai clicar no seu PC de verdade.\nPara parar: botão PARAR, Esc 3x, Ctrl+Alt+Q ou mouse num canto da tela.')) return;
  mostrarControle(quer);
};
async function cliqueNaTela(a) {
  if (!controleLigado) { toast('Os cliques na tela estão DESLIGADOS. Ligue no botão grande à esquerda.'); return; }
  try {
    if (a.tipo !== 'rolar') await cena.animarAcao(a);
    if (doNavegador()) {
      const L = (navInfo && navInfo.largura) || 1280, A = (navInfo && navInfo.altura) || 800;
      if (a.tipo === 'rolar') await api().navegador_acao('rolar', a.valor);
      else for (let i = a.tipo === 'duplo' ? 2 : 1; i > 0; i--) await api().navegador_acao('clicar', a.u * L, a.v * A);
      return;
    }
    const r = await api().notebook_acao(a.tipo, a.u, a.v, a.valor === undefined ? null : a.valor);
    if (r && r.erro) {
      toast('Não deu: ' + r.erro);
      if (/fail|canto|safe/i.test(r.erro)) mostrarControle(false);   // freio do canto: tudo desligado
    }
  } catch (_) {
  } finally { cena.fimAcao(); }
}

// ---------- parar ----------
async function parar(motivo) {
  cena.fimAcao(); mostrarControle(false);
  try { await api().notebook_acao('parar'); } catch (_) {}
  toast('PARADO: ' + motivo);
}
$('parar').onclick = () => parar('botão PARAR');
$('pausar').onclick = () => api().notebook_acao('pausar');
$('retomar').onclick = () => api().notebook_acao('retomar');
let escs = [];
addEventListener('keydown', ev => {
  if (ev.key === 'Escape') { const t = performance.now(); escs = escs.filter(x => t - x < 1500).concat(t); if (escs.length >= 3) { escs = []; parar('Esc×3'); } }
  if (ev.ctrlKey && ev.altKey && ev.key.toLowerCase() === 'q') parar('Ctrl+Alt+Q');
  if (ev.key === 'F11') { ev.preventDefault(); try { api().tela_cheia(); } catch (_) {} }
  if (ev.code === 'Space' && document.activeElement !== $('entrada')) { ev.preventDefault(); try { api().ouvir_agora(); } catch (_) {} }
});

// ---------- microfone, painel completo, abas ----------
function micEstado(ligado) { $('mic').textContent = ligado ? 'Microfone ativo' : 'Microfone pausado'; $('mic').classList.toggle('desligado', !ligado); }
$('falar').onclick = () => { try { api().ouvir_agora(); } catch (_) {} };
$('mic').onclick = async () => { try { micEstado(await api().alternar_microfone()); } catch (_) {} };
$('classico').onclick = () => { location.href = '../index.html'; };
$('aba-fechar').onclick = () => funcoes.fecharAba();

// ---------- sistema: dados reais do notebook ----------
async function atualizarStatus() {
  if (document.hidden || !api() || !api().status) return;
  try {
    const s = await api().status();
    $('s-cpu').textContent = s.cpu + '%'; $('s-ram').textContent = s.ram + '%';
    $('s-bat').textContent = s.bateria == null ? '—' : s.bateria + '%' + (s.carregando ? ' ⚡' : '');
  } catch (_) {}
}

// ---------- início ----------
addEventListener('error', e => { try { api().erro_js(`Quarto 3D: ${e.message} (linha ${e.lineno})`); } catch (_) {} });
function iniciar() {
  if (iniciar.feito || !api() || !api().pronto) return;
  iniciar.feito = true;
  atualizarStatus(); setInterval(atualizarStatus, 2500);
  setInterval(buscarQuadro, 140);
  setInterval(lerEstado, 450);
  api().pronto();
}
addEventListener('pywebviewready', iniciar);
iniciar();
