// Quarto do Braga em 3D: o Ryker sentado no ThinkPad. A tela do ThinkPad espelha a tela REAL do PC (os quadros
// chegam pelo main.js, do mini notebook do Braga) e cliques nela viram cliques no PC (só com os cliques LIGADOS).
// Modelo feito no Blender (assets/jarvis_v5.glb).
// Mãos de verdade: cinemática inversa (CCD) leva a mão direita ao mouse da mesa (que anda junto com o cursor do PC)
// e os dedos às teclas quando alguém digita. Leve para PC com pouca memória e vídeo Intel: sombras calculadas uma
// vez só, tela do notebook em 1280x720 sem mipmaps, até 30 quadros por segundo e resolução que se ajusta sozinha.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const B = (x, y, z) => new THREE.Vector3(x, z, -y);   // coordenadas Blender (Z pra cima) -> three.js
const V = (x, y, z) => new THREE.Vector3(x, y, z);

// Onde ficam as coisas na mesa (espaço do mundo, medido no jarvis_v5.glb)
const TECLADO = { L: [V(-1.125, .789, -1.088), V(-1.015, .789, -1.142)], R: [V(-0.985, .789, -1.088), V(-0.875, .789, -1.142)] };
// Quanto o mouse anda no mousepad de um canto ao outro da tela (metros) e onde ele fica parado: um pouco mais perto
// do Ryker que no modelo, senão o braço dele não alcança o canto de cima do mousepad.
const MOUSE_CURSO = { x: .05, z: .038 }, MOUSE_PERTO = V(-.03, 0, .035);

export function criarCena(canvas, aoCarregar) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  let escala = 1;   // resolução de desenho: cai sozinha se o PC não aguentar 30 quadros por segundo
  renderer.setPixelRatio(escala);
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
  // cursorAlvo = onde está o mouse de verdade (o cursor 3D e o mouse da mesa vão até lá suavemente)
  const estado = { nivel: 0, falando: false, gesto: 0, modo: 'live5d', cursor: null, cursorAlvo: null, acao: null, hover: null,
    controle: false, agente: false, digitarAte: 0, mouseAte: 0, cliqueEm: 0, rolarAte: 0, fps: 0, escala: 1 };
  const R = { ossos: {}, rest: {}, morph: [] };
  let pronto = false, cam5Pos = new THREE.Vector3(-0.02, 1.62, 0.2), telaObj = null, telaC = new THREE.Vector3(), telaN = new THREE.Vector3(0, 0, 1), telaUp = new THREE.Vector3(0, 1, 0), webcamPos = B(-.76, 1.22, 1.12), cabecaPos = B(-1, .5, 1.3);
  let mouseObj = null; const mouseRepouso = V(-0.67, .765, -.98);

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
      if (m && m.name === 'TelaAoVivo') { o.material = new THREE.MeshBasicMaterial({ map: tela.textura, toneMapped: false }); tela.montarCamada(o); o.castShadow = false; o.receiveShadow = false; telaObj = o; }
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
    mouseObj = raiz.getObjectByName('Mouse');
    if (mouseObj) {
      mouseObj.castShadow = false; mouseObj.userData.pos0 = mouseObj.position.clone();
      new THREE.Box3().setFromObject(mouseObj).getCenter(mouseObj.userData.centro0 = V(0, 0, 0));
      mouseRepouso.copy(mouseObj.userData.centro0).add(MOUSE_PERTO);
    }
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
    maos:   () => ({ pos: V(-0.52, 1.28, -0.58), alvo: V(-0.86, .80, -1.06), fov: 46, auto: false }),   // mãos, teclado, mouse e tela
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
  function dedo(L, f, v, y = 0) { gira(`Finger${f}_${L}`, v, y); }
  // dedos com ossos separados (Finger0..3, 0 = indicador): leve defasagem entre eles = movimento natural
  function dedos(L, v, y = 0) { for (let f = 0; f < 4; f++) dedo(L, f, v * (1 + (f - 1.5) * .12), y); }
  function morph(nome, v) { for (const m of R.morph) { const i = m.morphTargetDictionary[nome]; if (i !== undefined) m.morphTargetInfluences[i] = v; } }

  // ---------- cinemática inversa (CCD): gira antebraço e braço até o "efetor" (mão ou dedo) chegar no alvo ----------
  const _P = V(0, 0, 0), _E = V(0, 0, 0), _a = V(0, 0, 0), _b = V(0, 0, 0), _eixo = V(0, 0, 0);
  const _qW = new THREE.Quaternion(), _qB = new THREE.Quaternion(), _qP = new THREE.Quaternion();
  const _base = [new THREE.Quaternion(), new THREE.Quaternion()], _ik = [new THREE.Quaternion(), new THREE.Quaternion()];
  function maoAte(L, efetorNome, alvo, peso) {
    const cadeia = [R.ossos['ForeArm_' + L], R.ossos['UpperArm_' + L]], efetor = R.ossos[efetorNome];
    if (!cadeia[0] || !cadeia[1] || !efetor || peso < .002) return;
    R.ossos.Hips.updateMatrixWorld(true);
    cadeia.forEach((o, i) => _base[i].copy(o.quaternion));
    for (let volta = 0; volta < 8; volta++) {
      for (const osso of cadeia) {
        osso.getWorldPosition(_P); efetor.getWorldPosition(_E);
        _a.subVectors(_E, _P).normalize(); _b.subVectors(alvo, _P).normalize();
        const ang = Math.acos(THREE.MathUtils.clamp(_a.dot(_b), -1, 1));
        if (ang < 1e-3) continue;
        _eixo.crossVectors(_a, _b); if (_eixo.lengthSq() < 1e-12) continue; _eixo.normalize();
        _qW.setFromAxisAngle(_eixo, Math.min(ang, .2));
        osso.getWorldQuaternion(_qB); osso.parent.getWorldQuaternion(_qP);
        osso.quaternion.copy(_qP.invert().multiply(_qW.multiply(_qB)));
        osso.updateMatrixWorld(true);
      }
    }
    cadeia.forEach((o, i) => { _ik[i].copy(o.quaternion); o.quaternion.copy(_base[i]).slerp(_ik[i], peso); });
    R.ossos.Hips.updateMatrixWorld(true);
  }

  // dedos pulando de tecla em tecla enquanto alguém digita
  const digit = { L: { de: V(0, 0, 0), para: V(0, 0, 0), agora: V(0, 0, 0), t0: 0, dur: 1, dedo: 0, iniciado: false }, R: { de: V(0, 0, 0), para: V(0, 0, 0), agora: V(0, 0, 0), t0: 0, dur: 1, dedo: 1, iniciado: false } };
  function alvoTecla(L, agora) {
    const d = digit[L], [a, b] = TECLADO[L];
    if (!d.iniciado) { d.para.lerpVectors(a, b, .5); d.agora.copy(d.para); d.iniciado = true; }
    if (agora - d.t0 > d.dur) {   // próxima tecla
      d.de.copy(d.agora); d.t0 = agora; d.dur = 120 + Math.random() * 110; d.dedo = Math.floor(Math.random() * 4);
      d.para.set(a.x + (b.x - a.x) * Math.random(), a.y, a.z + (b.z - a.z) * Math.random());
    }
    const p = Math.min(1, (agora - d.t0) / d.dur), e = p * p * (3 - 2 * p);
    d.agora.lerpVectors(d.de, d.para, e);
    d.agora.y = a.y + Math.sin(Math.min(1, p / .8) * Math.PI) * .016;   // levanta o dedo entre as teclas
    d.batendo = p > .78;
    return d.agora;
  }

  let piscarAte = 0, proxPiscar = 2, pesoMouse = 0, pesoTecladoL = 0, pesoTecladoR = 0;
  const alvoMao = V(0, 0, 0), posMouse = V(0, 0, 0);
  function animar(t, dt) {
    const n = estado.nivel, f = estado.falando, agora = performance.now();
    // piscar e boca valem em qualquer pose
    if (t > proxPiscar) { piscarAte = t + .13; proxPiscar = t + 2 + Math.random() * 3.5; }
    morph('Piscar', t < piscarAte ? 1 : 0);
    morph('Fala', Math.min(1, n * 1.2));
    estado.gesto += ((f ? 1 : 0) - estado.gesto) * Math.min(1, dt * 3); const g = estado.gesto;

    // cursor: a ação animada manda; senão vai suave até o mouse de verdade
    const A = estado.acao;
    let p = 0;
    if (A) {
      p = Math.min(1, (agora - A.t0) / A.dur); const e = p < .5 ? 2 * p * p : 1 - (-2 * p + 2) ** 2 / 2;
      if (A.de && A.para) estado.cursor = [A.de[0] + (A.para[0] - A.de[0]) * e, A.de[1] + (A.para[1] - A.de[1]) * e];
      if (p >= 1 && !A.feito) { A.feito = true; A.resolve(); }
    } else if (estado.cursorAlvo) {
      if (!estado.cursor) estado.cursor = estado.cursorAlvo.slice();
      const k = Math.min(1, dt * 10);
      estado.cursor = [estado.cursor[0] + (estado.cursorAlvo[0] - estado.cursor[0]) * k, estado.cursor[1] + (estado.cursorAlvo[1] - estado.cursor[1]) * k];
    }
    const digitando = A ? A.tipo === 'digitar' : agora < estado.digitarAte;
    const noMouse = A ? A.tipo !== 'digitar' : (agora < estado.mouseAte || agora < estado.rolarAte);
    const clicando = A ? p > .8 : agora - estado.cliqueEm < 200;
    pesoMouse += ((noMouse && !digitando ? 1 : 0) - pesoMouse) * Math.min(1, dt * 6);
    pesoTecladoL += ((digitando ? 1 : 0) - pesoTecladoL) * Math.min(1, dt * 8);
    pesoTecladoR += ((digitando && pesoMouse < .5 ? 1 : 0) - pesoTecladoR) * Math.min(1, dt * 8);
    const ux = (estado.cursor ? estado.cursor[0] : .5) - .5, vy = (estado.cursor ? estado.cursor[1] : .5) - .5;

    // corpo: respira; inclina pra frente digitando e pro lado do mouse
    const resp = Math.sin(t * 1.7), frente = Math.max(pesoMouse, pesoTecladoL) * .06;
    gira('Spine', resp * .012 + frente);
    gira('Chest', resp * .018 - g * .05 + frente * .5, Math.sin(t * .9) * g * .06 - pesoMouse * .07);
    gira('Neck', .05 * (1 - g) + Math.sin(t * .6) * .02, -g * .1);
    // cabeça: olha a tela (e acompanha o cursor); falando, olha pra câmera e acena
    gira('Head', (1 - g) * .12 + g * (Math.sin(t * 4.2) * .05 + n * .06) - .04 - Math.max(pesoMouse, pesoTecladoL) * .18,
      -g * .32 + Math.sin(t * .45) * .06 * (1 - pesoMouse) + g * Math.sin(t * 1.3) * .08 - ux * .18 * pesoMouse, g * Math.sin(t * 1.1) * .05);

    // braços na pose de base (modelada digitando) ou gesticulando ao falar
    const gs = Math.sin(t * 2.4), gs2 = Math.sin(t * 1.3 + 1), solto = 1 - Math.max(pesoMouse, pesoTecladoR);
    gira('UpperArm_R', g * solto * (.12 + gs2 * .06), 0, -g * solto * (.25 + gs * .06));
    gira('ForeArm_R', g * solto * (.42 + gs * .15), g * solto * .35);
    gira('Hand_R', g * solto * gs * .3, g * solto * .6);
    gira('UpperArm_L', g * (1 - pesoTecladoL) * .15 * Math.max(0, gs2), 0, 0); gira('ForeArm_L', g * (1 - pesoTecladoL) * .25 * Math.max(0, gs2));
    gira('Hand_L', 0);

    // mouse da mesa: anda junto com o cursor do PC (só quando a mão está nele)
    if (mouseObj) {
      posMouse.set(mouseRepouso.x + ux * 2 * MOUSE_CURSO.x * pesoMouse, mouseRepouso.y, mouseRepouso.z + vy * 2 * MOUSE_CURSO.z * pesoMouse);
      if (agora < estado.rolarAte) posMouse.z += Math.sin(t * 18) * .002;
      const local = mouseObj.parent.worldToLocal(posMouse.clone()).sub(mouseObj.parent.worldToLocal(mouseObj.userData.centro0.clone()));
      mouseObj.position.copy(mouseObj.userData.pos0).add(local);
    }
    // mão direita no mouse: palma em cima, dedos nos botões; o indicador aperta no clique
    if (pesoMouse > .002) {
      alvoMao.copy(posMouse).add(V(0, .03, .055 - (clicando ? 0 : 0)));
      if (clicando) alvoMao.y -= .004;
      maoAte('R', 'Hand_R', alvoMao, pesoMouse);
      gira('Hand_R', -.1 * pesoMouse, .25 * pesoMouse, 0);
      dedos('R', .35 * pesoMouse);
      dedo('R', 0, (clicando ? .75 : .3) * pesoMouse + (agora < estado.rolarAte ? Math.max(0, Math.sin(t * 20)) * .4 : 0));
    }
    // digitando: os dedos vão de tecla em tecla e batem
    for (const [L, peso] of [['L', pesoTecladoL], ['R', pesoTecladoR]]) {
      if (peso < .002) continue;
      const alvo = alvoTecla(L, agora);
      maoAte(L, `Finger1_${L}`, alvo, peso);
      dedos(L, .25 * peso);
      if (digit[L].batendo) dedo(L, digit[L].dedo, .75 * peso);
    }
    // parado: digita devagar com os dedos, que param quando ele gesticula
    if (!digitando && pesoMouse < .5) {
      for (const [L, ph] of [['L', 0], ['R', 1.7]]) {
        const tp = Math.max(0, Math.sin(t * 9 + ph)) * Math.max(0, Math.sin(t * 1.3 + ph * 2)) * .6;
        const k = L === 'R' ? 1 - g : 1 - g * .5;
        dedos(L, tp * .35 * k);
      }
    }
  }

  // ---------- desenho: até 30 por segundo, resolução que se ajusta ao PC ----------
  // A resolução só fica menor se isso deixou o quarto mais rápido de verdade; se não ajudou (o gargalo é outro),
  // volta para a anterior e para de tentar baixar. Assim a imagem não fica borrada à toa.
  const relogio = new THREE.Clock();
  let ultimo = 0, contagem = 0, gastoJs = 0, inicioJanela = performance.now(), lentas = 0, rapidas = 0, tentativa = null, piso = .55;
  const gl = renderer.getContext(), info = gl.getExtension('WEBGL_debug_renderer_info');
  estado.placa = info ? gl.getParameter(info.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER);
  function mudarEscala(nova) { escala = estado.escala = +nova.toFixed(2); renderer.setPixelRatio(escala); renderer.setSize(innerWidth, innerHeight); }
  function ajustarResolucao(fps) {
    estado.fps = Math.round(fps);
    if (tentativa) {   // a última redução ajudou?
      if (fps < tentativa.fps * 1.15) { piso = tentativa.escala; mudarEscala(tentativa.escala); }
      tentativa = null; lentas = rapidas = 0; return;
    }
    if (fps < 24) { lentas++; rapidas = 0; } else if (fps > 28) { rapidas++; lentas = 0; } else lentas = rapidas = 0;
    if (lentas >= 2 && escala - .15 >= piso - 1e-6) { tentativa = { fps, escala }; mudarEscala(escala - .15); lentas = 0; }
    else if (rapidas >= 5 && escala < 1) { mudarEscala(Math.min(1, escala + .15)); rapidas = 0; }
  }
  (function loop(agora) {
    requestAnimationFrame(loop);
    if (document.hidden || agora - ultimo < 28) return;   // ~30 quadros por segundo numa tela de 60 Hz; minimizado, nada
    ultimo = agora;
    const t0 = performance.now(), dt = Math.min(.1, relogio.getDelta()), t = relogio.elapsedTime;
    if (pronto) animar(t, dt);
    tela.desenhar(t, estado);
    controls.update(); renderer.render(scene, camera);
    gastoJs += performance.now() - t0; contagem++;
    if (agora - inicioJanela > 2000) {
      estado.msQuadro = +(gastoJs / contagem).toFixed(1);
      ajustarResolucao(contagem * 1000 / (agora - inicioJanela)); contagem = 0; gastoJs = 0; inicioJanela = agora;
    }
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
  // o que está acontecendo de verdade no PC (vem do registro do mini notebook); ms = quanto tempo dura
  function evento(tipo, ms) {
    const agora = performance.now();
    if (tipo === 'digitar') estado.digitarAte = Math.max(estado.digitarAte, agora + (ms || 1200));
    if (tipo === 'clicar') { estado.cliqueEm = agora; estado.mouseAte = agora + 2000; if (estado.cursor) tela.clique(...estado.cursor); }
    if (tipo === 'mouse') estado.mouseAte = agora + 1800;
    if (tipo === 'rolar') { estado.rolarAte = agora + 900; estado.mouseAte = agora + 2000; }
  }
  // foto do que a câmera vê agora (para conferir as animações sem precisar olhar a janela)
  function foto() { renderer.render(scene, camera); return renderer.domElement.toDataURL('image/jpeg', .8); }
  return { estado, vista, animarAcao, fimAcao, evento, foto, aoClicarTela: f => ouvintes.push(f), quadro: bmp => tela.frame(bmp), aviso: t => { tela.erro = t; } };
}

// A tela do ThinkPad tem duas camadas:
// - fundo: um canvas de 960x540 que só é redesenhado (e reenviado à placa de vídeo) quando chega um quadro novo
//   do PC, ~9 por segundo. (Mandar o ImageBitmap direto para a textura deixava a tela parada no vídeo Intel.)
// - marcas (cursor grande, anel, cliques, faixa de estado): um canvas pequeno e transparente por cima, só
//   redesenhado quando alguma marca muda.
function criarTelaNotebook(renderer) {
  const preparar = t => { t.flipY = false; t.colorSpace = THREE.SRGBColorSpace; t.minFilter = THREE.LinearFilter; t.generateMipmaps = false; return t; };
  const W = 960, H = 540;
  const fundo = document.createElement('canvas'); fundo.width = W; fundo.height = H;
  const f = fundo.getContext('2d'), textura = preparar(new THREE.CanvasTexture(fundo));
  textura.anisotropy = Math.min(4, renderer.capabilities.getMaxAnisotropy());
  const cv = document.createElement('canvas'); cv.width = W; cv.height = H;
  const c = cv.getContext('2d'), camada = preparar(new THREE.CanvasTexture(cv));
  let temQuadro = false, erroDesenhado, cliques = [], ultimo = -1;
  function desenharAguardo() {
    f.fillStyle = '#0a1f5c'; f.fillRect(0, 0, W, H); f.fillStyle = '#fff'; f.textAlign = 'center';
    f.font = 'bold 40px sans-serif'; f.fillText('Ligando a tela do seu PC...', W / 2, H / 2);
    f.font = '24px sans-serif'; f.fillText(api.erro || 'mini notebook do Braga', W / 2, H / 2 + 46);
    erroDesenhado = api.erro; textura.needsUpdate = true;
  }
  const api = {
    textura, erro: null,
    montarCamada(tela) {   // mesma malha da tela, logo à frente dela
      const m = new THREE.Mesh(tela.geometry, new THREE.MeshBasicMaterial({ map: camada, transparent: true, depthWrite: false,
        toneMapped: false, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 }));
      m.renderOrder = 2; tela.add(m);
    },
    frame(bmp) {   // quadro novo da tela do PC (já reduzido para 960x540 ao abrir o JPEG)
      f.drawImage(bmp, 0, 0, W, H); bmp.close();
      textura.needsUpdate = true; temQuadro = true; api.erro = null;
    },
    clique(u, v) { cliques.push({ u, v, t: performance.now() }); },
    desenhar(t, e) {
      if (!temQuadro && erroDesenhado !== api.erro) desenharAguardo();
      const q = Math.floor(t * 20); if (q === ultimo) return; ultimo = q;   // marcas: até 20 por segundo
      const agora = performance.now(); cliques = cliques.filter(o => agora - o.t < 700);
      const marca = `${e.cursor && e.cursor.map(v => v.toFixed(3))}|${e.hover}|${e.controle}|${e.agente}|${!!e.acao}|${cliques.length}`;
      if (!cliques.length && marca === api.marca) return;   // nada mudou: nem redesenha nem reenvia
      api.marca = marca;
      c.clearRect(0, 0, W, H);
      const k = W / 1920;   // as marcas foram pensadas para 1920 de largura
      // hover do senhor: anel bem visível onde o clique vai cair
      if (e.hover) { const [x, y] = [e.hover[0] * W, e.hover[1] * H];
        c.lineWidth = 6 * k; c.strokeStyle = e.controle ? '#33ff77' : '#ffcc00'; c.beginPath(); c.arc(x, y, 34 * k, 0, 7); c.stroke();
        c.beginPath(); c.moveTo(x - 50 * k, y); c.lineTo(x - 20 * k, y); c.moveTo(x + 20 * k, y); c.lineTo(x + 50 * k, y); c.moveTo(x, y - 50 * k); c.lineTo(x, y - 20 * k); c.moveTo(x, y + 20 * k); c.lineTo(x, y + 50 * k); c.stroke(); }
      // ondas de clique
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
      camada.needsUpdate = true;
    },
  };
  return api;
}
