// Avatar 3D do Braga: um personagem (cabelo vermelho espetado, moletom e máscara pretos) numa mesa, mexendo no
// notebook. Tudo é desenhado com formas simples do Three.js (leve para o PC). Ele reage ao que acontece de verdade:
// - digitar (Braga ou o senhor): as mãos batem no teclado;
// - o mouse de verdade: a mão direita vai para o touchpad e acompanha o cursor; clique e rolagem também aparecem;
// - falando: a cabeça acompanha a fala; pensando: inclina a cabeça; parado: respira.
// A tela do notebook dele mostra o PC ao vivo enquanto o Braga controla (ou a fábrica roda no navegador do Braga);
// fora disso, um editor de código. Clicar na tela dele abre o mini notebook.
// Usa as variáveis do script principal (estadoAtual, nivel, tarefaAtiva, ultimaAtividade, nb, falarAgora).
(function () {
  if (typeof THREE === "undefined") return;
  const avatar = { ligado: false };
  window.avatar = avatar;

  let renderer, cena, camera, canvas, telaMesh, telaCanvas, telaCtx, telaTex;
  const corpo = {}, bracos = {};
  const telaImg = new Image();
  let ultimoQuadro = 0, numeroQuadro = "", buscandoQuadro = false;
  let estadoNb = null, ultimoEstado = 0, acoesVistas = "";
  let digitarAte = 0, cliqueEm = 0, rolarAte = 0, mouseAte = 0;
  const cursor = { x: 0.5, y: 0.5 }, cursorAntes = { x: 0.5, y: 0.5 };
  const v = (x, y, z) => new THREE.Vector3(x, y, z);

  // ---------- peças (estilo anime: sombreado de desenho em 3 tons e contorno preto) ----------
  let gradiente = null;
  function tonsDeAnime() {
    gradiente = new THREE.DataTexture(new Uint8Array([60, 150, 255]), 3, 1, THREE.LuminanceFormat);
    gradiente.minFilter = gradiente.magFilter = THREE.NearestFilter;
    gradiente.needsUpdate = true;
  }
  const mat = (cor, _rugosidade, _metal, extra = {}) =>
    new THREE.MeshToonMaterial({ color: cor, gradientMap: gradiente, ...extra });
  const tintaContorno = new THREE.MeshBasicMaterial({ color: 0x05060a, side: THREE.BackSide });
  function contornar(mesh, k = 1.07) {  // o "traço" do desenho: uma cópia preta, um pouco maior, por dentro
    const traco = new THREE.Mesh(mesh.geometry, tintaContorno);
    traco.scale.setScalar(k);
    mesh.add(traco);
    return mesh;
  }
  const caixa = (l, a, p, m) => new THREE.Mesh(new THREE.BoxGeometry(l, a, p), m);
  const cilindro = (r1, r2, h, m, seg = 16) => new THREE.Mesh(new THREE.CylinderGeometry(r1, r2, h, seg), m);
  const esfera = (r, m, seg = 20) => new THREE.Mesh(new THREE.SphereGeometry(r, seg, seg), m);

  function textura(largura, altura, desenhar) {
    const c = document.createElement("canvas");
    c.width = largura; c.height = altura;
    desenhar(c.getContext("2d"), largura, altura);
    const t = new THREE.CanvasTexture(c);
    t.anisotropy = 4;
    return t;
  }

  function montarSala() {
    cena.add(new THREE.HemisphereLight(0x4a6fb3, 0x05070c, 0.55));
    const luzTela = new THREE.PointLight(0x5b8cff, 1.4, 2.2);
    luzTela.position.set(0.1, 1.0, 0.1);
    cena.add(luzTela);
    const luzFundo = new THREE.PointLight(0x2b4f9e, 0.7, 6);
    luzFundo.position.set(-1.6, 2.2, -1.2);
    cena.add(luzFundo);
    const luzLado = new THREE.DirectionalLight(0x8fb3ff, 0.35);
    luzLado.position.set(-2, 3, 2);
    cena.add(luzLado);
    // contorno azul por trás (separa o moletom preto do fundo) e um preenchimento suave do lado da câmera
    const contorno = new THREE.DirectionalLight(0x4d7dff, 1.1);
    contorno.position.set(-1.6, 2.0, -1.8);
    cena.add(contorno);
    const preenchimento = new THREE.DirectionalLight(0xc7d6ff, 0.45);
    preenchimento.position.set(2.2, 1.8, 1.8);
    cena.add(preenchimento);

    const chao = caixa(8, 0.02, 8, mat(0x0b0f18));
    chao.position.y = -0.01;
    cena.add(chao);
    const parede = caixa(8, 3.2, 0.05, mat(0x111a2c));
    parede.position.set(0, 1.6, -1.4);
    cena.add(parede);
    for (const [x, y] of [[-1.3, 2.0], [-0.6, 2.15], [0.9, 2.0]]) {  // quadros escuros na parede
      const quadro = caixa(0.42, 0.55, 0.01, mat(0x070a12, 0.6));
      quadro.position.set(x, y, -1.37);
      cena.add(quadro);
    }
    const cama = caixa(1.9, 0.45, 1.1, mat(0x1b2741));
    cama.position.set(-1.9, 0.22, -0.6);
    cena.add(cama);
    const travesseiro = caixa(0.6, 0.12, 0.4, mat(0x24345a));
    travesseiro.position.set(-1.6, 0.52, -0.95);
    cena.add(travesseiro);
  }

  function montarMesa() {
    const madeira = mat(0x2a1d14, 0.7);
    const tampo = caixa(1.7, 0.05, 0.85, madeira);
    tampo.position.set(0.1, 0.725, -0.05);
    cena.add(tampo);
    for (const [x, z] of [[-0.7, -0.4], [0.9, -0.4], [-0.7, 0.32], [0.9, 0.32]]) {
      const perna = caixa(0.05, 0.7, 0.05, madeira);
      perna.position.set(x, 0.35, z);
      cena.add(perna);
    }
    // caneca preta
    const caneca = cilindro(0.045, 0.042, 0.13, mat(0x0d0d10, 0.5, 0.3), 24);
    caneca.position.set(-0.5, 0.815, -0.22);
    cena.add(caneca);
    const rotulo = new THREE.Mesh(new THREE.CylinderGeometry(0.046, 0.043, 0.06, 24, 1, true),
      new THREE.MeshBasicMaterial({ map: textura(256, 64, (g, l, a) => {
        g.fillStyle = "#0d0d10"; g.fillRect(0, 0, l, a);
        g.fillStyle = "#c9ced8"; g.font = "bold 30px Segoe UI"; g.fillText("BRAGA", 70, 42);
      }) }));
    rotulo.position.copy(caneca.position);
    rotulo.rotation.y = 2.2;
    cena.add(rotulo);
  }

  function montarNotebook() {
    const notebook = new THREE.Group();
    notebook.position.set(0.1, 0.75, -0.03);
    notebook.rotation.y = -0.24;  // de frente para o personagem
    cena.add(notebook);
    corpo.notebook = notebook;
    const cinza = mat(0x3a3a41, 0.45, 0.6);
    const base = caixa(0.34, 0.016, 0.235, cinza);
    base.position.y = 0.008;
    notebook.add(base);
    // teclado desenhado numa textura (leve), com a área do touchpad
    const teclado = new THREE.Mesh(new THREE.PlaneGeometry(0.3, 0.115), new THREE.MeshStandardMaterial({
      roughness: 0.9, map: textura(512, 196, (g, l, a) => {
        g.fillStyle = "#16161a"; g.fillRect(0, 0, l, a);
        const linhas = 6, colunas = 15;
        for (let i = 0; i < linhas; i++) for (let j = 0; j < colunas; j++) {
          if (i === 5 && j > 3 && j < 10) continue;
          g.fillStyle = "#2b2b31";
          g.fillRect(6 + j * 33.5, 6 + i * 31.5, 29, 26);
        }
        g.fillRect(6 + 4 * 33.5, 6 + 5 * 31.5, 6 * 33.5 - 4, 26);  // barra de espaço
      }) }));
    teclado.rotation.x = -Math.PI / 2;
    teclado.position.set(0, 0.0165, -0.035);
    notebook.add(teclado);
    const touchpad = new THREE.Mesh(new THREE.PlaneGeometry(0.11, 0.06), mat(0x46464e, 0.5, 0.3));
    touchpad.rotation.x = -Math.PI / 2;
    touchpad.position.set(0, 0.0166, 0.07);
    notebook.add(touchpad);
    // tampa com a tela ao vivo
    const dobradica = new THREE.Group();
    dobradica.position.set(0, 0.016, -0.117);
    dobradica.rotation.x = -0.24;
    notebook.add(dobradica);
    const tampa = caixa(0.34, 0.225, 0.008, cinza);
    tampa.position.y = 0.1125;
    dobradica.add(tampa);
    telaCanvas = document.createElement("canvas");
    telaCanvas.width = 960; telaCanvas.height = 600;
    telaCtx = telaCanvas.getContext("2d");
    telaTex = new THREE.CanvasTexture(telaCanvas);
    telaMesh = new THREE.Mesh(new THREE.PlaneGeometry(0.318, 0.199), new THREE.MeshBasicMaterial({ map: telaTex }));
    telaMesh.position.set(0, 0.116, 0.0045);
    dobradica.add(telaMesh);
    const logo = new THREE.Mesh(new THREE.PlaneGeometry(0.05, 0.012), new THREE.MeshBasicMaterial({
      transparent: true, map: textura(128, 32, (g) => { g.fillStyle = "#8b8b93"; g.font = "600 22px Segoe UI"; g.fillText("Lenovo", 28, 24); }) }));
    logo.position.set(0, 0.008, 0.0045);
    dobradica.add(logo);
    corpo.alvos = {  // pontos do notebook onde as mãos vão (no espaço do notebook)
      teclaE: v(-0.075, 0.03, -0.035), teclaD: v(0.06, 0.03, -0.035),
      descansoE: v(-0.095, 0.026, 0.07), descansoD: v(0.095, 0.026, 0.07),
      touchpad: v(0, 0.026, 0.07),
    };
  }

  function olhoDeAnime() {  // olho grande: branco, íris azul brilhante, pupila, dois brilhos e cílio grosso
    return textura(128, 96, (g, l, a) => {
      g.clearRect(0, 0, l, a);
      g.fillStyle = "#f4f7ff";
      g.beginPath(); g.ellipse(64, 54, 50, 34, 0, 0, Math.PI * 2); g.fill();
      const iris = g.createRadialGradient(64, 50, 4, 64, 54, 30);
      iris.addColorStop(0, "#9be7ff"); iris.addColorStop(0.55, "#2f8cff"); iris.addColorStop(1, "#0b2a6b");
      g.fillStyle = iris;
      g.beginPath(); g.ellipse(64, 56, 25, 31, 0, 0, Math.PI * 2); g.fill();
      g.fillStyle = "#050814";
      g.beginPath(); g.ellipse(64, 58, 10, 14, 0, 0, Math.PI * 2); g.fill();
      g.fillStyle = "#ffffff";
      g.beginPath(); g.arc(54, 44, 8, 0, Math.PI * 2); g.fill();
      g.beginPath(); g.arc(74, 68, 4, 0, Math.PI * 2); g.fill();
      g.strokeStyle = "#050814"; g.lineWidth = 9; g.lineCap = "round";
      g.beginPath(); g.ellipse(64, 56, 52, 36, 0, Math.PI * 1.08, Math.PI * 1.92); g.stroke();
    });
  }

  function montarPersonagem() {
    const moletom = mat(0x0d1018), pele = mat(0xf0c4a8), preto = mat(0x07080c);
    const cabelo = mat(0xff2a3a, 0, 0, { emissive: 0x4a0710 });
    const pessoa = new THREE.Group();
    pessoa.position.set(0.0, 0, 0.4);
    pessoa.rotation.y = -0.24;  // virado um pouco para a câmera: dá para ver o rosto de lado
    cena.add(pessoa);
    corpo.pessoa = pessoa;
    // cadeira
    const assento = caixa(0.46, 0.05, 0.44, mat(0x1a1d26));
    assento.position.set(0, 0.47, 0.06);
    pessoa.add(assento);
    const encosto = caixa(0.44, 0.55, 0.05, mat(0x1a1d26));
    encosto.position.set(0, 0.8, 0.29);
    encosto.rotation.x = 0.12;
    pessoa.add(encosto);
    // pernas (para baixo da mesa)
    for (const lado of [-1, 1]) {
      const coxa = cilindro(0.07, 0.065, 0.42, preto);
      coxa.rotation.x = Math.PI / 2;
      coxa.position.set(lado * 0.1, 0.55, -0.12);
      pessoa.add(coxa);
      const canela = cilindro(0.055, 0.05, 0.45, preto);
      canela.position.set(lado * 0.1, 0.3, -0.32);
      pessoa.add(canela);
    }
    // tronco inclinado para o notebook
    const tronco = new THREE.Group();
    tronco.position.set(0, 0.52, 0.05);
    tronco.rotation.x = -0.32;
    pessoa.add(tronco);
    corpo.tronco = tronco;
    const peito = contornar(cilindro(0.16, 0.2, 0.5, moletom, 20), 1.05);
    peito.position.y = 0.27;
    peito.scale.z = 0.72;
    tronco.add(peito);
    for (const lado of [-1, 1]) {
      const ombro = contornar(esfera(0.085, moletom));
      ombro.position.set(lado * 0.18, 0.47, 0);
      tronco.add(ombro);
    }
    const capuz = contornar(esfera(0.14, moletom, 18), 1.05);
    capuz.position.set(0, 0.55, 0.07);
    capuz.scale.set(1.05, 0.7, 0.8);
    tronco.add(capuz);
    corpo.ombroE = new THREE.Object3D(); corpo.ombroE.position.set(-0.19, 0.45, -0.01); tronco.add(corpo.ombroE);
    corpo.ombroD = new THREE.Object3D(); corpo.ombroD.position.set(0.19, 0.45, -0.01); tronco.add(corpo.ombroD);
    // cabeça (com a máscara e o cabelo espetado)
    const pescoco = new THREE.Group();
    pescoco.position.set(0, 0.56, -0.02);
    tronco.add(pescoco);
    corpo.cabeca = pescoco;
    const gola = contornar(cilindro(0.085, 0.095, 0.11, preto));
    gola.position.y = 0.04;
    pescoco.add(gola);
    // cabeça grande, proporção de anime
    const cabeca = contornar(esfera(0.13, pele, 28), 1.05);
    cabeca.position.y = 0.19;
    cabeca.scale.set(0.95, 1.04, 1);
    pescoco.add(cabeca);
    const mascara = contornar(new THREE.Mesh(new THREE.CylinderGeometry(0.129, 0.12, 0.11, 28, 1, true),
      mat(0x0c0d12, 0, 0, { side: THREE.DoubleSide })), 1.04);
    mascara.position.set(0, 0.135, -0.004);
    pescoco.add(mascara);
    corpo.olhos = [];
    const texturaOlho = olhoDeAnime();
    for (const lado of [-1, 1]) {
      const orelha = contornar(esfera(0.026, pele, 10));
      orelha.position.set(lado * 0.124, 0.19, 0.01);
      orelha.scale.set(0.5, 1, 0.8);
      pescoco.add(orelha);
      const olho = new THREE.Mesh(new THREE.PlaneGeometry(0.06, 0.045),
        new THREE.MeshBasicMaterial({ map: texturaOlho, transparent: true }));
      olho.position.set(lado * 0.05, 0.205, -0.121);
      olho.rotation.set(0, Math.PI + lado * -0.42, 0);  // virado para frente, acompanhando a curva do rosto
      pescoco.add(olho);
      corpo.olhos.push(olho);
      const sobrancelha = caixa(0.05, 0.008, 0.006, preto);
      sobrancelha.position.set(lado * 0.05, 0.245, -0.12);
      sobrancelha.rotation.set(0, lado * 0.42, lado * -0.12);
      pescoco.add(sobrancelha);
    }
    // cabelo de anime: mechas grandes, pontudas e jogadas para trás, mais a franja
    const mechas = new THREE.Group();
    mechas.position.y = 0.19;
    pescoco.add(mechas);
    let semente = 11;
    const sorte = () => ((semente = (semente * 9301 + 49297) % 233280) / 233280);
    const mecha = (normal, direcao, grossura, comprimento) => {
      const m = contornar(new THREE.Mesh(new THREE.ConeGeometry(grossura, comprimento, 4), cabelo), 1.08);
      const ponta = direcao.normalize();
      m.quaternion.setFromUnitVectors(v(0, 1, 0), ponta);
      m.position.copy(normal.clone().multiplyScalar(0.11)).add(ponta.clone().multiplyScalar(comprimento * 0.35));
      mechas.add(m);
    };
    for (let i = 0; i < 46; i++) {
      const fi = sorte() * Math.PI * 2, teta = sorte() * 1.35;
      const normal = v(Math.sin(teta) * Math.cos(fi), Math.cos(teta), Math.sin(teta) * Math.sin(fi));
      if (normal.z < -0.45 && normal.y < 0.75) continue;  // o rosto fica livre (a franja vem abaixo)
      mecha(normal, normal.clone().add(v((sorte() - 0.5) * 0.5, 0.35, 0.55)), 0.04 + sorte() * 0.018, 0.17 + sorte() * 0.11);
    }
    for (const x of [-0.07, -0.025, 0.025, 0.07]) {  // franja caindo na testa
      const normal = v(x * 4, 0.6, -0.75).normalize();
      mecha(normal, v(x * 2, -0.75, -0.5), 0.032, 0.13);
    }
    // braços: posicionados a cada quadro (cinemática inversa simples de dois ossos)
    for (const lado of ["E", "D"]) {
      const braco = contornar(cilindro(0.048, 0.052, 1, moletom), 1.1);
      const antebraco = contornar(cilindro(0.042, 0.048, 1, moletom), 1.1);
      const mao = contornar(caixa(0.07, 0.024, 0.085, pele), 1.12);
      const punho = cilindro(0.046, 0.046, 0.03, preto);
      for (const m of [braco, antebraco, mao, punho]) cena.add(m);
      bracos[lado] = { braco, antebraco, mao, punho, alvo: v(0, 0, 0), pronto: false };
    }
  }

  // ---------- braços ----------
  function entre(mesh, a, b) {  // estica um cilindro entre dois pontos
    const dir = b.clone().sub(a);
    mesh.position.copy(a).add(b).multiplyScalar(0.5);
    mesh.scale.set(1, dir.length(), 1);
    mesh.quaternion.setFromUnitVectors(v(0, 1, 0), dir.normalize());
  }

  function posicionarBraco(lado, alvo) {
    const b = bracos[lado], ombro = new THREE.Vector3();
    corpo["ombro" + lado].getWorldPosition(ombro);
    const L1 = 0.29, L2 = 0.27;
    const ate = alvo.clone().sub(ombro);
    const d = Math.min(ate.length(), L1 + L2 - 0.005);
    const dir = ate.normalize();
    const x = (L1 * L1 - L2 * L2 + d * d) / (2 * d), h = Math.sqrt(Math.max(0, L1 * L1 - x * x));
    const polo = v(lado === "E" ? -1 : 1, -0.9, 0.6);  // cotovelo para fora e para baixo
    polo.sub(dir.clone().multiplyScalar(polo.dot(dir))).normalize();
    const cotovelo = ombro.clone().add(dir.clone().multiplyScalar(x)).add(polo.multiplyScalar(h));
    const punho = ombro.clone().add(dir.clone().multiplyScalar(d));
    entre(b.braco, ombro, cotovelo);
    entre(b.antebraco, cotovelo, punho);
    b.punho.position.copy(punho);
    b.punho.quaternion.copy(b.antebraco.quaternion);
    const frente = punho.clone().sub(cotovelo).setY(0).normalize();
    b.mao.position.copy(punho).add(frente.multiplyScalar(0.045)).add(v(0, -0.008, 0));
    b.mao.rotation.set(0, Math.atan2(frente.x, frente.z), 0);
  }

  function pontoNotebook(local) { return corpo.notebook.localToWorld(local.clone()); }

  // ---------- tela do notebook dele ----------
  const LINHAS_DE_CODIGO = [];
  for (let i = 0; i < 80; i++) {
    LINHAS_DE_CODIGO.push({ recuo: [0, 1, 1, 2, 2, 3][i % 6] * 28, partes: Array.from({ length: 2 + (i * 7) % 4 },
      (_, j) => ({ larg: 30 + ((i * 13 + j * 29) % 110), cor: ["#c792ea", "#82aaff", "#c3e88d", "#ffcb6b", "#89ddff", "#d6deeb"][(i + j * 3) % 6] })) });
  }

  function desenharTela(t) {
    const g = telaCtx, L = telaCanvas.width, A = telaCanvas.height;
    if (avatar.aoVivo && telaImg.naturalWidth) {
      g.fillStyle = "#000"; g.fillRect(0, 0, L, A);
      const escala = Math.min(L / telaImg.naturalWidth, A / telaImg.naturalHeight);
      const w = telaImg.naturalWidth * escala, h = telaImg.naturalHeight * escala;
      g.drawImage(telaImg, (L - w) / 2, (A - h) / 2, w, h);
      g.fillStyle = "rgba(245,158,11,.9)"; g.fillRect(0, 0, L, 6);  // faixa: ao vivo
      telaTex.needsUpdate = true;
      return;
    }
    // editor de código (o Braga "trabalhando")
    g.fillStyle = "#0b1020"; g.fillRect(0, 0, L, A);
    g.fillStyle = "#111a2e"; g.fillRect(0, 0, 170, A);
    g.fillStyle = "#16213a"; g.fillRect(0, 0, L, 34);
    g.fillStyle = "#8ea3c4"; g.font = "600 16px Segoe UI";
    g.fillText("BRAGA  ·  " + ((typeof tarefaAtiva !== "undefined" && tarefaAtiva) ? (ultimaAtividade || "trabalhando") : "pronto"), 14, 23);
    for (let i = 0; i < 12; i++) { g.fillStyle = i === 3 ? "#3d8bff" : "#2a3858"; g.fillRect(16, 56 + i * 30, 110 - (i * 17) % 50, 10); }
    const rodando = typeof tarefaAtiva !== "undefined" && tarefaAtiva;
    const inicio = Math.floor((rodando ? t / 260 : t / 2200)) % 40;
    for (let i = 0; i < 17; i++) {
      const linha = LINHAS_DE_CODIGO[(inicio + i) % LINHAS_DE_CODIGO.length];
      let x = 196 + linha.recuo;
      g.fillStyle = "#3b4a6b"; g.font = "14px Consolas"; g.fillText(String(inicio + i + 1).padStart(3, " "), 176 - 2, 66 + i * 31);
      for (const p of linha.partes) { g.fillStyle = p.cor; g.fillRect(x, 56 + i * 31, p.larg, 12); x += p.larg + 12; }
    }
    if (Math.floor(t / 500) % 2) { g.fillStyle = "#e6eefc"; g.fillRect(196 + 120, 56 + 16 * 31, 3, 16); }
    telaTex.needsUpdate = true;
  }

  async function buscarQuadro() {  // quadro ao vivo do PC (ou do navegador do Braga, se é lá que está rodando)
    if (buscandoQuadro || !window.pywebview?.api?.notebook_info) return;
    buscandoQuadro = true;
    try {
      if (!nb.info) nb.info = await pywebview.api.notebook_info();
      const info = doNavegador() ? (nb.navInfo || await pywebview.api.navegador_info()) : nb.info;
      const r = await fetch(`${info.quadro}?n=${numeroQuadro}&t=${Date.now()}`, { cache: "no-store" });
      if (r.ok) {
        numeroQuadro = r.headers.get("X-Quadro") || "";
        if (r.status === 200) {
          const url = URL.createObjectURL(await r.blob()), antiga = telaImg.src;
          telaImg.src = url;
          if (antiga.startsWith("blob:")) setTimeout(() => URL.revokeObjectURL(antiga), 1000);
        }
      }
    } catch (_) {}
    buscandoQuadro = false;
  }

  // ---------- o que está acontecendo (para animar) ----------
  avatar.evento = (tipo) => {  // chamado pelo mini notebook quando o senhor mexe nele
    const agora = performance.now();
    if (["digitar", "tecla"].includes(tipo)) digitarAte = agora + 900;
    if (["clicar", "duplo", "direito", "tocar", "tocar_duplo"].includes(tipo)) { cliqueEm = agora; mouseAte = agora + 1500; }
    if (tipo === "deslizar") mouseAte = agora + 1500;
    if (tipo === "rolar") { rolarAte = agora + 700; mouseAte = agora + 1500; }
  };

  async function lerEstado() {
    if (!window.pywebview?.api?.notebook_estado) return;
    try {
      estadoNb = await pywebview.api.notebook_estado();
    } catch (_) { return; }
    if (estadoNb.cursor) {
      cursor.x = estadoNb.cursor[0]; cursor.y = estadoNb.cursor[1];
      if (Math.abs(cursor.x - cursorAntes.x) + Math.abs(cursor.y - cursorAntes.y) > 0.004) mouseAte = performance.now() + 1500;
      cursorAntes.x = cursor.x; cursorAntes.y = cursor.y;
    }
    const acoes = estadoNb.acoes || [];
    const marca = acoes.length ? acoes[0].hora + acoes[0].texto : "";
    if (marca && marca !== acoesVistas) {
      const novas = [];
      for (const a of acoes) { if (a.hora + a.texto === acoesVistas) break; novas.push(a.texto); }
      acoesVistas = marca;
      for (const texto of novas) {
        if (/^(Digitou|Tecla|Senhor digitou|Senhor: tecla)/.test(texto)) avatar.evento("digitar");
        else if (/^(Clique|Senhor: (clicar|duplo|direito|tocar))/.test(texto)) avatar.evento("clicar");
        else if (/^Rolou/.test(texto)) avatar.evento("rolar");
      }
      mostrarAtividade(acoes);
    }
    // a tela dele é o PC de verdade, sempre ao vivo (com o Braga por cima e as janelas atrás dele)
    avatar.aoVivo = true;
  }

  // de onde vem a imagem da tela dele: o PC de verdade, ou o navegador do Braga quando a fábrica roda lá
  const doNavegador = () => nb.fonte === "navegador" && typeof tarefaAtiva !== "undefined" && tarefaAtiva;

  // ---------- cartões de vidro ----------
  function mostrarAtividade(acoes) {
    const ul = document.querySelector("#av-atividade");
    if (!ul) return;
    ul.innerHTML = "";
    for (const a of acoes.slice(0, 5)) {
      const li = document.createElement("li");
      li.innerHTML = `<i></i><b>${a.hora.slice(0, 5)}</b>`;
      li.append(a.texto);
      ul.append(li);
    }
  }

  function mostrarPensamento() {
    const el = document.querySelector("#av-pensamento");
    if (!el) return;
    const texto = (typeof tarefaAtiva !== "undefined" && tarefaAtiva && ultimaAtividade) ? ultimaAtividade
      : document.querySelector("#bolha-texto")?.textContent || "";
    if (el.textContent !== texto) el.textContent = texto;
    document.querySelector("#av-foco").style.width = (typeof tarefaAtiva !== "undefined" && tarefaAtiva ? 72 : 18) + "%";
  }

  // ---------- animação ----------
  const suave = (atual, alvo, k) => atual.lerp(alvo, k);
  let ultimoDesenho = 0, ultimaTela = 0;

  function animar(t) {
    requestAnimationFrame(animar);
    if (!avatar.ligado) return;
    const comPagina = document.body.classList.contains("com-pagina");
    const intervalo = comPagina ? 200 : 33;  // ~30 quadros por segundo; com uma aba aberta, quase parado
    if (t - ultimoDesenho < intervalo) return;
    ultimoDesenho = t;
    if (t - ultimoEstado > 450) { ultimoEstado = t; lerEstado(); mostrarPensamento(); }
    if (avatar.aoVivo && t - ultimoQuadro > 140) { ultimoQuadro = t; buscarQuadro(); }
    if (t - ultimaTela > 66) { ultimaTela = t; desenharTela(t); }

    const agora = performance.now();
    const rodando = typeof tarefaAtiva !== "undefined" && tarefaAtiva;
    const digitando = agora < digitarAte || (rodando && Math.sin(t / 1700) > -0.2);
    const noMouse = agora < mouseAte && !digitando;
    // mão esquerda: teclado (digitando) ou descanso
    const A = corpo.alvos;
    const batida = (fase) => Math.max(0, Math.sin(t / 55 + fase)) * 0.012;
    const ruido = (fase) => v(Math.sin(t / 130 + fase) * 0.018, 0, Math.cos(t / 170 + fase) * 0.012);
    const alvoE = digitando ? A.teclaE.clone().add(ruido(0)).add(v(0, batida(0), 0)) : A.descansoE.clone();
    let alvoD;
    if (noMouse) {  // mão direita no touchpad, seguindo o cursor de verdade
      alvoD = A.touchpad.clone().add(v((cursor.x - 0.5) * 0.08, 0, (cursor.y - 0.5) * 0.045));
      if (agora - cliqueEm < 140) alvoD.y -= 0.009;
      if (agora < rolarAte) alvoD.z += Math.sin(t / 60) * 0.008;
    } else {
      alvoD = digitando ? A.teclaD.clone().add(ruido(2)).add(v(0, batida(1.7), 0)) : A.descansoD.clone();
    }
    for (const [lado, alvo] of [["E", alvoE], ["D", alvoD]]) {
      const b = bracos[lado], mundo = pontoNotebook(alvo);
      if (!b.pronto) { b.alvo.copy(mundo); b.pronto = true; }
      suave(b.alvo, mundo, digitando ? 0.5 : 0.16);
      posicionarBraco(lado, b.alvo);
    }
    // corpo: respira, inclina; cabeça olha a tela, acompanha a fala e inclina pensando
    const falandoAgora = typeof estadoAtual !== "undefined" && estadoAtual === "falando";
    const pensando = typeof estadoAtual !== "undefined" && estadoAtual === "pensando";
    corpo.tronco.rotation.x = -0.32 + Math.sin(t / 1400) * 0.012 + (pensando ? 0.05 : 0);
    corpo.tronco.scale.y = 1 + Math.sin(t / 900) * 0.008;
    const fala = falandoAgora ? (typeof nivel !== "undefined" ? nivel : 0.3) : 0;
    corpo.cabeca.rotation.x = 0.28 + Math.sin(t / 2100) * 0.03 + fala * 0.12 * Math.sin(t / 90);
    corpo.cabeca.rotation.z = pensando ? 0.16 : Math.sin(t / 3000) * 0.03;
    corpo.cabeca.rotation.y = noMouse ? (cursor.x - 0.5) * 0.25 : Math.sin(t / 2600) * 0.05;
    const piscando = (t % 4200) < 130;  // pisca a cada ~4 segundos
    for (const olho of corpo.olhos) olho.scale.y = piscando ? 0.1 : 1;
    renderer.render(cena, camera);
  }

  // ---------- encaixe na janela: o personagem fica no meio da área central ----------
  function redimensionar() {
    const L = innerWidth, A = innerHeight;
    renderer.setSize(L, A, false);
    camera.aspect = L / A;
    const centro = document.querySelector(".centro")?.getBoundingClientRect();
    const deslocamento = centro ? (centro.left + centro.width / 2) - L / 2 : 0;
    camera.setViewOffset(L, A, -deslocamento, -A * 0.08, L, A);  // desce a cena: a cabeça não encosta no topo
    camera.updateProjectionMatrix();
  }

  // a tela do notebook dele é o PC de verdade: clicar nela clica no PC (clique, duplo, direito, rodinha).
  // Fora da tela, clicar é falar (como a esfera).
  function pontoNaTela(e) {
    if (!avatar.ligado || document.body.classList.contains("com-pagina")) return undefined;
    const r = canvas.getBoundingClientRect();
    const raio = new THREE.Raycaster();
    raio.setFromCamera({ x: ((e.clientX - r.left) / r.width) * 2 - 1, y: -((e.clientY - r.top) / r.height) * 2 + 1 }, camera);
    const acerto = raio.intersectObject(telaMesh)[0];
    return acerto ? { x: acerto.uv.x, y: 1 - acerto.uv.y } : null;  // a imagem preenche a tela inteira (16:10)
  }

  function agirNaTela(tipo, p, valor = null) {
    avatar.evento(tipo);
    if (doNavegador()) {
      const L = nb.navInfo?.largura || 1280, A = nb.navInfo?.altura || 800;
      if (tipo === "rolar") return pywebview.api.navegador_acao("rolar", valor);
      pywebview.api.navegador_acao("clicar", p.x * L, p.y * A);
      if (tipo === "duplo") pywebview.api.navegador_acao("clicar", p.x * L, p.y * A);
      return;
    }
    pywebview.api.notebook_acao(tipo, p?.x ?? null, p?.y ?? null, valor);
  }

  let cliqueAgendado = null;
  function aoClicar(e) {
    const p = pontoNaTela(e);
    if (p === undefined) return;
    if (!p) { if (typeof falarAgora === "function") falarAgora(); return; }
    clearTimeout(cliqueAgendado);  // espera um pouco: se vier o segundo clique, vira clique duplo
    cliqueAgendado = setTimeout(() => agirNaTela("clicar", p), 260);
  }
  function aoClicarDuplo(e) {
    const p = pontoNaTela(e);
    if (!p) return;
    clearTimeout(cliqueAgendado);
    agirNaTela("duplo", p);
  }
  function aoBotaoDireito(e) {
    const p = pontoNaTela(e);
    if (!p) return;
    e.preventDefault();
    agirNaTela("direito", p);
  }
  let rolagem = 0, rolando = false;
  function aoRolar(e) {
    const p = pontoNaTela(e);
    if (!p) return;
    e.preventDefault();
    rolagem += e.deltaY;
    if (rolando) return;
    rolando = true;
    setTimeout(() => { agirNaTela("rolar", p, Math.round(rolagem)); rolagem = 0; rolando = false; }, 150);
  }

  avatar.iniciar = () => {
    canvas = document.querySelector("#avatar3d");
    renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
    renderer.setPixelRatio(1);  // leve para o PC
    cena = new THREE.Scene();
    cena.fog = new THREE.Fog(0x050b16, 2.5, 6);
    // câmera de lado, um pouco atrás do ombro direito: o personagem à esquerda e o notebook à direita
    camera = new THREE.PerspectiveCamera(30, 1, 0.05, 30);
    camera.position.set(2.05, 1.7, 1.55);
    camera.lookAt(0.02, 0.9, 0.02);
    avatar.camera = camera;
    tonsDeAnime();
    montarSala(); montarMesa(); montarNotebook(); montarPersonagem();
    redimensionar();
    addEventListener("resize", redimensionar);
    const reator = document.querySelector(".reator");
    reator.addEventListener("click", aoClicar);
    reator.addEventListener("dblclick", aoClicarDuplo);
    reator.addEventListener("contextmenu", aoBotaoDireito);
    reator.addEventListener("wheel", aoRolar, { passive: false });
    requestAnimationFrame(animar);
  };

  avatar.ligar = (sim) => {
    avatar.ligado = !!sim;
    document.body.classList.toggle("avatar", avatar.ligado);
    if (avatar.ligado) setTimeout(redimensionar, 50);
    try { localStorage.setItem("braga-visual", avatar.ligado ? "avatar" : "esfera"); } catch (_) {}
  };
})();
