// Quarto do Braga em 3D: o Ryker sentado no ThinkPad. A tela do ThinkPad espelha a tela REAL do PC (os quadros
// chegam pelo main.js, do mini notebook do Braga) e cliques nela viram cliques no PC (só com os cliques LIGADOS).
// Modelo feito no Blender (assets/jarvis_v5.glb). Ajustado para PC com pouca memória e vídeo Intel: pixel 1:1,
// sombras calculadas uma vez só, tela do notebook em 1280x720 e no máximo 30 quadros por segundo.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const B = (x, y, z) => new THREE.Vector3(x, z, -y);   // coordenadas Blender (Z pra cima) -> three.js

export function criarCena(canvas, aoCarregar) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(1);
  renderer.setSize(innerWidth, innerHeight);
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.shadowMap.autoUpdate = false;   // a sala não se mexe: sombra calculada ao carregar
  renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.05;
  const scene = new THREE.Scene(); scene.background = new THREE.Color(0x05080f);
  const pm = new THREE.PMREMGenerator(renderer); scene.environment = pm.fromScene(new RoomEnvironment(), .04).texture;   // reflexos PBR do notebook

  const camera = new THREE.PerspectiveCamera(50, innerWidth / innerHeight, .01, 50);
  const controls = new OrbitControls(camera, canvas); controls.enableDamping = true;
  controls.minDistance = .25; controls.maxDistance = 3.2; controls.autoRotateSpeed = 1.6;

  // Luzes: plafon quente, brilho azul da tela, luar pela janela, ambiente
  scene.add(new THREE.HemisphereLight(0xa8bfff, 0x2a2420, 1.1));
  const teto = new THREE.PointLight(0xffe2c0, 5, 9, 1.2); teto.position.copy(B(0, 0, 2.4)); teto.castShadow = true;
  teto.shadow.mapSize.set(1024, 1024); teto.shadow.bias = -.004; teto.shadow.normalBias = .03; scene.add(teto);
  const telaLuz = new THREE.PointLight(0x7fb8ff, 1.2, 1.6, 1.5); telaLuz.position.copy(B(-1, 1.0, 1.0)); scene.add(telaLuz);
  const preench = new THREE.DirectionalLight(0xfff0e6, .9); preench.position.copy(B(.5, -1.2, 2)); preench.target.position.copy(B(-1, .5, 1.1));
  scene.add(preench, preench.target);
  const lua = new THREE.PointLight(0x6080ff, 1.5, 3); lua.position.copy(B(.85, 1.2, 1.5)); scene.add(lua);

  const tela = criarTelaNotebook(renderer);
  // controle = cliques do senhor na tela 3D liberados; agente = o Braga está mexendo no PC sozinho
  const estado = { nivel: 0, falando: false, gesto: 0, modo: 'live5d', cursor: null, acao: null, hover: null,
    controle: false, agente: false, digitarAte: 0, mouseAte: 0, cliqueEm: 0 };
  const R = { ossos: {}, rest: {}, morph: [] };
  let pronto = false, cam5Pos = new THREE.Vector3(-0.02, 1.62, 0.2), telaObj = null, telaC = new THREE.Vector3(), telaN = new THREE.Vector3(0, 0, 1), telaUp = new THREE.Vector3(0, 1, 0), webcamPos = B(-.76, 1.22, 1.12), cabecaPos = B(-1, .5, 1.3);

  const grad = new THREE.DataTexture(new Uint8Array([90, 90, 90, 255, 175, 175, 175, 255, 255, 255, 255, 255]), 3, 1);
  grad.minFilter = grad.magFilter = THREE.NearestFilter; grad.needsUpdate = true;
  const contorno = new THREE.MeshBasicMaterial({ color: 0x120808, side: THREE.BackSide });
  contorno.onBeforeCompile = s => { s.vertexShader = s.vertexShader.replace('#include <begin_vertex>', '#include <begin_vertex>\n transformed += normalize(normal) * 0.0022;'); };

  new GLTFLoader().load('assets/jarvis_v5.glb', gltf => {
    const raiz = gltf.scene; const extras = [];
    raiz.traverse(o => {
      if (o.isBone) { R.ossos[o.name] = o; R.rest[o.name] = o.quaternion.clone(); }
      if (!o.isMesh) return;
      o.castShadow = true; o.receiveShadow = true;
      const m = o.material;
      if (m && m.name && m.name.startsWith('Ryker_')) {   // visual anime: toon + contorno
        const t = new THREE.MeshToonMaterial({ color: m.color, map: m.map, gradientMap: grad, name: m.name });
        if (m.emissive && m.emissive.getHex()) { t.emissive = m.emissive; t.emissiveIntensity = 1; }
        o.material = t; o.receiveShadow = false;
        if (!/Olhos|Boca|Nariz|Brilho|Emblema/.test(o.name + m.name)) extras.push(o);
      }
      if (o.morphTargetDictionary) R.morph.push(o);
      if (m && m.name === 'TelaAoVivo') { tela.textura.flipY = false; o.material = new THREE.MeshBasicMaterial({ map: tela.textura, toneMapped: false }); o.castShadow = false; o.receiveShadow = false; telaObj = o; }
      else if (m && m.name && m.name.startsWith('TP_') && m.isMeshStandardMaterial) m.envMapIntensity = .7;
      if (m && /Vidro|LuzTeto|LedBranco/.test(m.name)) o.castShadow = false;
    });
    for (const o of extras) {   // contorno "inverted hull" (funciona também na malha com ossos)
      let c;
      if (o.isSkinnedMesh) { c = new THREE.SkinnedMesh(o.geometry, contorno); c.bind(o.skeleton, o.bindMatrix); }
      else c = new THREE.Mesh(o.geometry, contorno);
      c.position.copy(o.position); c.quaternion.copy(o.quaternion); c.scale.copy(o.scale);
      if (o.morphTargetInfluences) { c.morphTargetInfluences = o.morphTargetInfluences; c.morphTargetDictionary = o.morphTargetDictionary; }
      c.castShadow = false; o.parent.add(c);
    }
    scene.add(raiz); raiz.updateMatrixWorld(true);
    const w = raiz.getObjectByName('WebcamOlho'); if (w) w.getWorldPosition(webcamPos);
    if (R.ossos.Head) { R.ossos.Head.getWorldPosition(cabecaPos); cabecaPos.y += .1; }
    const o5 = raiz.getObjectByName('Cam5DOlho'); if (o5) o5.getWorldPosition(cam5Pos);
    if (telaObj) {
      const g = telaObj.geometry, P = g.attributes.position, T = g.attributes.uv, c = {};
      for (let i = 0; i < T.count; i++) c[Math.round(T.getX(i)) + '' + Math.round(T.getY(i))] = new THREE.Vector3().fromBufferAttribute(P, i).applyMatrix4(telaObj.matrixWorld);
      const dx = c['10'].clone().sub(c['00']), dyBaixo = c['01'].clone().sub(c['00']);   // v cresce pra baixo
      telaC.copy(c['00']).addScaledVector(dx, .5).addScaledVector(dyBaixo, .5);
      telaUp.copy(dyBaixo).negate().normalize(); telaN.crossVectors(dx, telaUp).normalize();
      if (telaN.dot(cabecaPos.clone().sub(telaC)) < 0) telaN.negate();
    }
    pronto = true; renderer.shadowMap.needsUpdate = true; vista(estado.modo);
    if (aoCarregar) aoCarregar(null);
  }, undefined, e => { console.error('Falha ao carregar o modelo 3D', e); if (aoCarregar) aoCarregar(e); });

  const ombro = (d, up, dir, fov) => () => {
    const lado = new THREE.Vector3().crossVectors(telaUp, telaN).normalize();
    return { pos: telaC.clone().addScaledVector(telaN, d).addScaledVector(telaUp, up).addScaledVector(lado, dir), alvo: telaC.clone().addScaledVector(telaUp, -.015), fov, auto: false };
  };
  const VISTAS = {
    live5d: () => ({ pos: cam5Pos.clone(), alvo: telaC.clone().add(new THREE.Vector3(.0, .07, .3)), fov: 41, auto: false }),     // Live: câmera 5D no tripé
    medio:  () => ({ pos: cabecaPos.clone().add(new THREE.Vector3(.36, .1, .95)), alvo: telaC.clone().add(new THREE.Vector3(0, -.06, .25)), fov: 42, auto: false }), // Medium shot por trás
    close:  () => ({ pos: telaC.clone().addScaledVector(telaN, .62).addScaledVector(telaUp, .04).add(new THREE.Vector3(0, .16, 0)), alvo: telaC.clone().addScaledVector(telaUp, -.07), fov: 40, auto: false }), // tela + mãos
    ombro: ombro(1.0, .16, -.26, 26),     // por trás/por cima do ombro: tela grande e legível
    tela:  ombro(.62, .02, 0, 30),     // de frente pra tela (melhor para clicar)
    live:   () => ({ pos: webcamPos.clone(), alvo: cabecaPos.clone().add(new THREE.Vector3(.05, -.36, 0)), fov: 62, auto: false }),
    orbita: () => ({ pos: cabecaPos.clone().add(new THREE.Vector3(.9, .1, -.9)), alvo: cabecaPos.clone().add(new THREE.Vector3(0, -.3, 0)), fov: 55, auto: true }),
    quarto: () => ({ pos: B(-1.25, -1.35, 1.8), alvo: B(-.3, .6, .8), fov: 70, auto: false }),
    rosto:  () => ({ pos: cabecaPos.clone().add(new THREE.Vector3(.16, -.03, -.45)), alvo: cabecaPos.clone().add(new THREE.Vector3(0, -.04, 0)), fov: 35, auto: false }),
  };
  function vista(nome) {
    if (typeof nome === 'number') nome = Object.keys(VISTAS)[nome];
    if (!VISTAS[nome]) return;
    estado.modo = nome; const v = VISTAS[nome]();
    camera.position.copy(v.pos); controls.target.copy(v.alvo); camera.fov = v.fov; camera.updateProjectionMatrix();
    controls.autoRotate = v.auto; controls.update();
  }
  vista('live5d');

  addEventListener('resize', () => { camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); renderer.setSize(innerWidth, innerHeight); });

  const E = new THREE.Euler(), Q = new THREE.Quaternion();
  function gira(nome, x = 0, y = 0, z = 0) {
    const o = R.ossos[nome]; if (!o) return;
    o.quaternion.copy(R.rest[nome]).multiply(Q.setFromEuler(E.set(x, y, z)));
  }
  // dedos com ossos separados (Finger0..3): leve defasagem entre eles = movimento natural
  function dedos(L, v, y = 0) { for (let f = 0; f < 4; f++) gira(`Finger${f}_${L}`, v * (1 + (f - 1.5) * .12), y); }
  function morph(nome, v) { for (const m of R.morph) { const i = m.morphTargetDictionary[nome]; if (i !== undefined) m.morphTargetInfluences[i] = v; } }

  let piscarAte = 0, proxPiscar = 2;
  function animar(t, dt) {
    const n = estado.nivel, f = estado.falando;
    // piscar e boca valem em qualquer pose
    if (t > proxPiscar) { piscarAte = t + .13; proxPiscar = t + 2 + Math.random() * 3.5; }
    morph('Piscar', t < piscarAte ? 1 : 0);
    morph('Fala', Math.min(1, n * 1.2));
    estado.gesto += ((f ? 1 : 0) - estado.gesto) * Math.min(1, dt * 3); const g = estado.gesto;
    // respiração
    const resp = Math.sin(t * 1.7);
    gira('Spine', resp * .012); gira('Chest', resp * .018 - g * .05, Math.sin(t * .9) * g * .06);
    gira('Neck', .05 * (1 - g) + Math.sin(t * .6) * .02, -g * .1);

    // mexendo no PC: a animação de uma ação (clique na tela 3D) ou o que está acontecendo de verdade
    // (mouse andando, cliques e digitação, do senhor ou do Braga)
    const agora = performance.now(), A = estado.acao;
    let p = 0;
    if (A) {
      p = Math.min(1, (agora - A.t0) / A.dur); const e = p < .5 ? 2 * p * p : 1 - (-2 * p + 2) ** 2 / 2;
      if (A.de && A.para) estado.cursor = [A.de[0] + (A.para[0] - A.de[0]) * e, A.de[1] + (A.para[1] - A.de[1]) * e];
    }
    const digitando = A ? A.tipo === 'digitar' : agora < estado.digitarAte;
    const noMouse = A ? A.tipo !== 'digitar' : (agora < estado.mouseAte && !digitando);
    if (digitando || noMouse) {
      const ux = (estado.cursor ? estado.cursor[0] : .5) - .5, vy = (estado.cursor ? estado.cursor[1] : .5) - .5;
      gira('UpperArm_R', 0, 0, 0); gira('UpperArm_L', 0, 0, 0); gira('ForeArm_L', 0);
      if (noMouse) { gira('ForeArm_R', -.05, ux * .25, 0); gira('Hand_R', -.05 + vy * .12, ux * .35); }
      else { gira('ForeArm_R', 0); gira('Hand_R', 0); }
      const clicando = A ? p > .85 : agora - estado.cliqueEm < 180;
      dedos('R', digitando ? Math.max(0, Math.sin(t * 22)) * .4 : (clicando ? .45 : .1));
      dedos('L', digitando ? Math.max(0, Math.sin(t * 22 + 1.5)) * .4 : 0);
      gira('Head', .16 - g * .1, -ux * .15 - g * .2, 0);
      if (A && p >= 1 && !A.feito) { A.feito = true; A.resolve(); }
      return;
    }
    // cabeça: olha a tela; falando, olha pra câmera e acena
    gira('Head', (1 - g) * .12 + g * (Math.sin(t * 4.2) * .05 + n * .06) - .04, -g * .32 + Math.sin(t * .45) * .06 + g * Math.sin(t * 1.3) * .08, g * Math.sin(t * 1.1) * .05);
    // parado: digita devagar (dedos e mãos), que para quando ele gesticula
    for (const [L, ph] of [['L', 0], ['R', 1.7]]) {
      const tp = Math.max(0, Math.sin(t * 9 + ph)) * Math.max(0, Math.sin(t * 1.3 + ph * 2)) * .6;
      const k = L === 'R' ? 1 - g : 1 - g * .5;
      dedos(L, tp * .35 * k);
      gira('Hand_' + L, -tp * .08 * k);
    }
    // gestos ao falar: mão direita sobe e gesticula, esquerda acompanha de leve
    const gs = Math.sin(t * 2.4), gs2 = Math.sin(t * 1.3 + 1);
    gira('UpperArm_R', g * (.12 + gs2 * .06), 0, -g * (.25 + gs * .06));
    gira('ForeArm_R', g * (.42 + gs * .15), g * .35);
    gira('Hand_R', g * gs * .3, g * .6);
    gira('UpperArm_L', g * .15 * Math.max(0, gs2), 0, 0); gira('ForeArm_L', g * .25 * Math.max(0, gs2));
  }

  const relogio = new THREE.Clock();
  let ultimo = 0;
  (function loop(agora) {
    requestAnimationFrame(loop);
    if (document.hidden || agora - ultimo < 32) return;   // até ~30 quadros por segundo; minimizado, nada
    ultimo = agora;
    const dt = relogio.getDelta(), t = relogio.elapsedTime;
    if (pronto) animar(t, dt);
    tela.desenhar(t, estado);
    controls.update(); renderer.render(scene, camera);
  })(0);

  // ---------- clique/hover/rodinha direto na tela 3D ----------
  const ray = new THREE.Raycaster(), ndc = new THREE.Vector2();
  function uvDoPonteiro(ev) {
    if (!telaObj) return null;
    const r = canvas.getBoundingClientRect(); ndc.set((ev.clientX - r.left) / r.width * 2 - 1, -(ev.clientY - r.top) / r.height * 2 + 1);
    ray.setFromCamera(ndc, camera); const h = ray.intersectObject(telaObj)[0];
    return h && h.uv ? [h.uv.x, h.uv.y] : null;
  }
  let down = null; const ouvintes = [];
  const avisar = a => ouvintes.forEach(f => f(a));
  canvas.addEventListener('pointerdown', ev => { down = [ev.clientX, ev.clientY, ev.button]; });
  canvas.addEventListener('pointermove', ev => {
    estado.hover = uvDoPonteiro(ev); canvas.style.cursor = estado.hover ? 'crosshair' : '';
    controls.enableZoom = !(estado.hover && estado.controle);   // em cima da tela, a rodinha rola o PC
  });
  canvas.addEventListener('pointerup', ev => {
    if (!down || Math.hypot(ev.clientX - down[0], ev.clientY - down[1]) > 6) return;
    const uv = uvDoPonteiro(ev); if (uv) avisar({ tipo: down[2] === 2 ? 'direito' : 'clicar', u: uv[0], v: uv[1] });
  });
  canvas.addEventListener('dblclick', ev => { const uv = uvDoPonteiro(ev); if (uv) avisar({ tipo: 'duplo', u: uv[0], v: uv[1] }); });
  canvas.addEventListener('contextmenu', ev => { if (uvDoPonteiro(ev)) ev.preventDefault(); });
  let rolagem = 0, rolando = false;
  canvas.addEventListener('wheel', ev => {
    if (!estado.controle) return; const uv = uvDoPonteiro(ev); if (!uv) return;
    rolagem += ev.deltaY; if (rolando) return; rolando = true;
    setTimeout(() => { avisar({ tipo: 'rolar', u: uv[0], v: uv[1], valor: Math.round(rolagem) }); rolagem = 0; rolando = false; }, 150);
  }, { passive: true });

  // anima o Ryker + cursor 3D até o alvo; resolve quando a mão "clica"
  function animarAcao(a) {
    return new Promise(resolve => {
      const para = a.u !== undefined ? [a.u, a.v] : null;
      const dur = a.tipo === 'digitar' ? Math.min(4000, 500 + (a.texto || '').length * 45) : para ? 700 : 450;
      estado.acao = { tipo: a.tipo, t0: performance.now(), dur, de: estado.cursor || [.5, .5], para, resolve };
    }).then(() => { if (a.u !== undefined && a.tipo !== 'rolar') tela.clique(a.u, a.v); });
  }
  function fimAcao() { estado.acao = null; }
  // o que está acontecendo de verdade no PC (vem do registro do mini notebook)
  function evento(tipo) {
    const agora = performance.now();
    if (tipo === 'digitar') estado.digitarAte = agora + 1200;
    if (tipo === 'clicar') { estado.cliqueEm = agora; estado.mouseAte = agora + 1500; if (estado.cursor) tela.clique(...estado.cursor); }
    if (tipo === 'mouse' || tipo === 'rolar') estado.mouseAte = agora + 1500;
  }
  return { estado, vista, animarAcao, fimAcao, evento, aoClicarTela: f => ouvintes.push(f), quadro: bmp => tela.frame(bmp), aviso: t => { tela.erro = t; } };
}

function criarTelaNotebook(renderer) {
  const W = 1280, H = 720;
  const cv = document.createElement('canvas'); cv.width = W; cv.height = H;
  const c = cv.getContext('2d'); const textura = new THREE.CanvasTexture(cv);
  textura.colorSpace = THREE.SRGBColorSpace; textura.anisotropy = Math.min(4, renderer.capabilities.getMaxAnisotropy());
  textura.minFilter = THREE.LinearMipmapLinearFilter; textura.generateMipmaps = true;
  let quadro = null, cliques = [], ultimo = -1;
  const api = {
    textura, erro: null,
    frame(bmp) { if (quadro && quadro.close) quadro.close(); quadro = bmp; api.erro = null; },
    clique(u, v) { cliques.push({ u, v, t: performance.now() }); },
    desenhar(t, e) {
      const q = Math.floor(t * 15); if (q === ultimo) return; ultimo = q;   // 15 por segundo bastam
      if (quadro) c.drawImage(quadro, 0, 0, W, H);
      else {
        c.fillStyle = '#0a1f5c'; c.fillRect(0, 0, W, H); c.fillStyle = '#fff'; c.font = 'bold 40px sans-serif'; c.textAlign = 'center';
        c.fillText('Ligando a tela do seu PC...', W / 2, H / 2); c.font = '24px sans-serif'; c.fillText(api.erro || 'mini notebook do Braga', W / 2, H / 2 + 46); c.textAlign = 'left';
      }
      const k = W / 1920;   // as marcas foram pensadas para 1920 de largura
      // hover do senhor: anel bem visível onde o clique vai cair
      if (e.hover) { const [x, y] = [e.hover[0] * W, e.hover[1] * H];
        c.lineWidth = 6 * k; c.strokeStyle = e.controle ? '#33ff77' : '#ffcc00'; c.beginPath(); c.arc(x, y, 34 * k, 0, 7); c.stroke();
        c.beginPath(); c.moveTo(x - 50 * k, y); c.lineTo(x - 20 * k, y); c.moveTo(x + 20 * k, y); c.lineTo(x + 50 * k, y); c.moveTo(x, y - 50 * k); c.lineTo(x, y - 20 * k); c.moveTo(x, y + 20 * k); c.lineTo(x, y + 50 * k); c.stroke(); }
      // ondas de clique
      const agora = performance.now(); cliques = cliques.filter(o => agora - o.t < 700);
      for (const o of cliques) { const p = (agora - o.t) / 700; c.strokeStyle = `rgba(255,40,40,${1 - p})`; c.lineWidth = 10 * k; c.beginPath(); c.arc(o.u * W, o.v * H, (20 + p * 70) * k, 0, 7); c.stroke(); }
      // cursor 3D grande (posição real do mouse ou animação do Ryker)
      if (e.cursor) {
        const [x, y] = [e.cursor[0] * W, e.cursor[1] * H], s = 2.2 * k;
        c.save(); c.translate(x, y); c.scale(s, s); c.beginPath();
        c.moveTo(0, 0); c.lineTo(0, 22); c.lineTo(5.5, 17); c.lineTo(9.5, 26); c.lineTo(13, 24.5); c.lineTo(9, 16); c.lineTo(16, 16); c.closePath();
        c.fillStyle = '#fff'; c.fill(); c.lineWidth = 1.6; c.strokeStyle = '#000'; c.stroke(); c.restore();
        if (e.acao || e.agente) { c.fillStyle = 'rgba(255,40,40,.9)'; c.font = `bold ${30 * k}px sans-serif`; c.fillText('RYKER', x + 40 * k, y + 70 * k); }
      }
      // faixa de estado, bem visível
      const [cor, texto] = e.agente ? ['rgba(0,160,70,.85)', '● BRAGA CONTROLANDO O PC'] : e.controle ? ['rgba(0,160,70,.85)', '● CLIQUES LIGADOS'] : ['rgba(170,0,0,.85)', '■ CLIQUES DESLIGADOS'];
      c.fillStyle = cor; c.fillRect(W - 560 * k, 40 * k, 456 * k, 52 * k);
      c.fillStyle = '#fff'; c.font = `bold ${30 * k}px sans-serif`; c.fillText(texto, W - 542 * k, 77 * k);
      textura.needsUpdate = true;
    },
  };
  return api;
}
