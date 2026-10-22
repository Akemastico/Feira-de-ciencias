import * as THREE from 'three';
import { GLTFLoader } from '/vendor/three/GLTFLoader.js';

const EMOTIONS = ['neutro', 'feliz', 'triste', 'surpreso', 'curioso', 'bravo'];

// Textura de rosto por emoção (frontend/assets/rostos/N.png). O 1.png é a
// mesma imagem que já vem embutida no GLB, então o estado neutro é contínuo.
const FACES = {
  neutro: '/assets/rostos/1.png',
  feliz: '/assets/rostos/6.png',
  triste: '/assets/rostos/3.png',
  surpreso: '/assets/rostos/11.png',
  curioso: '/assets/rostos/10.png',
  bravo: '/assets/rostos/7.png',
};

// Nós do rig do modelo real (nomes de objeto do GLB).
const RIG_NODES = {
  spine: 'spine',
  shoulderL: 'shoulder.L',
  shoulderR: 'shoulder.R',
  upperArmL: 'upper_arm.L',
  upperArmR: 'upper_arm.R',
  forearmL: 'forearm.L',
  forearmR: 'forearm.R',
  handL: 'hand.L',
  handR: 'hand.R',
  rosto: 'rosto',
};

// Botões coloridos do BMO (nomes de nó no GLB). O "NurbsPath.001" são as
// pernas (verde escuro) e o "Cube.002"/"Cube.003" são os traços azuis do
// visor, então ficam de fora: aqui entram só os cinco botões.
const LED_NODES = ['NurbsPath.002', 'NurbsPath.003', 'NurbsPath.004', 'Plane', 'Plane.001'];

// Animações que o BMO sabe fazer. A lista é fechada: o nome chega pela rede.
const ANIMACOES = ['pular', 'dancar', 'tremer', 'acenar', 'olhar_lado', 'dormir'];

// Escala final do modelo: maior dimensão do GLB vira MODEL_SCALE.
const MODEL_SCALE = 2.2;

// O GLB vem com os braços em pose em T (esticados para o lado). Estes números
// foram medidos no navegador até os braços ficarem para baixo, encostados no
// tronco mas visíveis ao lado dele.
const ANGULO_BAIXO = Math.PI / 2; // 90°: tira o braço da pose em T
const ABERTURA = 0.2; // rad: abre o braço para fora (ombro -> mão)
const AFASTAMENTO = 0.24; // em unidades do GLB: tira o ombro de dentro do tronco
const BALANCO = 0.07; // rad: amplitude do balanço ocioso dos braços

// Eixo do mundo usado para girar os ombros.
const EIXO_Z = new THREE.Vector3(0, 0, 1);

// O three.js "limpa" o nome dos nós (tira ponto e barra), então o nome original
// do GLB fica em userData.name. É por ele que o rig e os botões são achados.
function porNome(model, nome) {
  let achado = null;
  model.traverse((o) => {
    if (!achado && o.userData?.name === nome) achado = o;
  });
  if (achado) return achado;
  // Reserva: tenta o nome já higienizado do three.js.
  return model.getObjectByName(nome.replace(/\s/g, '_').replace(/[\[\]\.:/\\]/g, ''));
}

// O GLTFLoader entrega o nó "rosto" como um grupo que embrulha a malha.
// O rig precisa da malha em si, porque é dela que sai a textura do rosto.
function primeiroMesh(obj) {
  if (!obj) return null;
  if (obj.isMesh) return obj;
  let achado = null;
  obj.traverse((o) => {
    if (!achado && o.isMesh) achado = o;
  });
  return achado;
}

// Materiais de uma malha: o three.js usa uma lista quando a malha tem mais
// de um material, e um material só quando tem um.
function materiaisDe(mesh) {
  const mat = mesh?.material;
  if (!mat) return [];
  return Array.isArray(mat) ? mat : [mat];
}

export class Bmo {
  constructor() {
    this.group = new THREE.Group();
    this.emotion = 'neutro';
    this.state = 'pronto';
    this._t = 0;
    this.model = null; // GLB carregado; null enquanto não carrega ou se falhar
    this.rig = {}; // nós do rig do modelo real
    this.leds = []; // botões coloríveis (do modelo ou do procedural)
    this._procedural = new THREE.Group();
    this._animation = null; // animação em andamento: { nome, inicio, duracao }
    this.ledColor = null; // cor do LED pedida pelo modelo
    this._ledPiscar = false; // o LED pisca enquanto a cor valer?
    this._emotionSince = 0; // quando a expressão atual começou
    this._faceToken = 0; // contador para descartar texturas de rosto atrasadas
    this._giro = new THREE.Quaternion(); // reuso do balanço dos braços
    this._buildProcedural();
    this._tryLoadGlb();
  }

  _buildProcedural() {
    const bodyMat = new THREE.MeshStandardMaterial({ color: 0x7ee0a8, roughness: 0.4, metalness: 0.05 });
    this.body = new THREE.Mesh(new THREE.BoxGeometry(1.0, 1.4, 0.8), bodyMat);

    const screenMat = new THREE.MeshBasicMaterial({ color: 0x111318 });
    this.screen = new THREE.Mesh(new THREE.PlaneGeometry(0.72, 0.62), screenMat);
    this.screen.position.set(0, 0.12, 0.405);

    this.canvas = document.createElement('canvas');
    this.canvas.width = 256;
    this.canvas.height = 256;
    this.ctx = this.canvas.getContext('2d');
    this.tex = new THREE.CanvasTexture(this.canvas);
    this.tex.colorSpace = THREE.SRGBColorSpace;
    const faceMat = new THREE.MeshBasicMaterial({ map: this.tex, transparent: true });
    this.face = new THREE.Mesh(new THREE.PlaneGeometry(0.72, 0.62), faceMat);
    this.face.position.set(0, 0.12, 0.41);

    const yellow = new THREE.MeshStandardMaterial({ color: 0xf5d76e, roughness: 0.3 });
    const b1 = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.16, 0.06), yellow);
    b1.position.set(-0.51, 0.1, 0.15);
    // Cada botão tem material próprio: colorir um LED não pode mexer no outro.
    const b2 = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.16, 0.06), yellow.clone());
    b2.position.set(-0.51, -0.12, 0.15);
    const b3 = new THREE.Mesh(
      new THREE.BoxGeometry(0.1, 0.08, 0.06),
      new THREE.MeshStandardMaterial({ color: 0xe05555 })
    );
    b3.position.set(-0.51, 0.42, 0.15);

    this._parts = [this.body, this.screen, this.face, b1, b2, b3];
    this._procedural.add(...this._parts);
    this.group.add(this._procedural);
    this.leds = [b1, b2, b3];
  }

  _tryLoadGlb() {
    const loader = new GLTFLoader();
    loader.load(
      '/assets/bmo.glb',
      (gltf) => {
        const model = gltf.scene;
        this.model = model;

        this.rig = {};
        for (const [chave, nome] of Object.entries(RIG_NODES)) {
          const obj = porNome(model, nome);
          this.rig[chave] = chave === 'rosto' ? primeiroMesh(obj) : (obj ?? null);
        }
        this.leds = this._collectLeds(model);

        // A cor do LED pode ter chegado antes do modelo carregar (o botão
        // fica pronto antes do GLB): repintar os botões do modelo.
        if (this.ledColor) this.setLed(this.ledColor, this._ledPiscar);

        // O BMO de código continua no grupo, mas escondido: só o rosto do
        // modelo real aparece na tela.
        this._procedural.visible = false;

        this._frameModel(model);
        this.group.add(model);

        // Deixa os braços para baixo (o GLB vem em pose em T) e esconde a laje
        // cinza solta, que é resíduo do Blender e invade o botão de falar.
        this._aplicarPoseDeRepouso();
        const laje = porNome(model, 'Cube.001');
        if (laje) laje.visible = false;

        // A emoção pode ter mudado enquanto o GLB carregava.
        this.setFace(FACES[this.emotion]);
      },
      undefined,
      () => { /* GLB ausente — mantém o BMO procedural */ }
    );
  }

  // Enquadramento: escala pela maior dimensão do modelo e centro em y = 0,
  // para o BMO ficar de pé e no meio da tela.
  _frameModel(model) {
    const box = new THREE.Box3().setFromObject(model);
    const size = box.getSize(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.y, size.z) || 1;
    model.scale.setScalar(MODEL_SCALE / maxDim);

    const scaled = new THREE.Box3().setFromObject(model);
    const center = scaled.getCenter(new THREE.Vector3());
    model.position.set(-center.x, -center.y, -center.z);
  }

  // Pose de repouso: baixa os braços (o GLB vem em pose em T), abre um pouco
  // para fora e afasta o ombro do tronco, para o braço aparecer ao lado do
  // corpo. Guarda a pose final em baseQuat: o balanço ocioso sempre recomeça
  // dela, senão a rotação acumularia e a pose desandaria com o tempo.
  _aplicarPoseDeRepouso() {
    for (const [chave, sinal] of [['shoulderL', 1], ['shoulderR', -1]]) {
      const ombro = this.rig[chave];
      if (!ombro) continue;
      // 1) baixa o braço (90° em torno do Z do mundo)
      ombro.rotateOnWorldAxis(EIXO_Z, sinal * ANGULO_BAIXO);
      // 2) abre um pouco para fora, para o braço ficar visível ao lado do corpo
      ombro.rotateOnWorldAxis(EIXO_Z, -sinal * ABERTURA);
      // 3) afasta o ombro da carcaça. O X local do spine aponta para o X
      //    contrário do mundo (o GLB está virado de costas), então o sinal é
      //    invertido para empurrar o ombro para fora do tronco.
      ombro.position.x -= sinal * AFASTAMENTO;
      ombro.updateWorldMatrix(true, false);
      ombro.userData.baseQuat = ombro.quaternion.clone();
      ombro.userData.eixoBalanco = this._eixoDoBalanco(ombro);
    }
  }

  // Eixo Z do mundo escrito no espaço local do ombro: é assim que o balanço
  // é aplicado sem acumular rotação a cada quadro.
  _eixoDoBalanco(ombro) {
    const pai = ombro.parent.getWorldQuaternion(new THREE.Quaternion());
    return EIXO_Z.clone()
      .applyQuaternion(pai.invert())
      .applyQuaternion(ombro.quaternion.clone().invert());
  }

  // Balanço ocioso dos braços, em torno do eixo Z do corpo (de fora para dentro
  // e vice-versa, sempre a partir da pose de repouso).
  _applyPose(t) {
    const balanco = Math.sin(t * 1.1) * BALANCO;
    for (const [chave, sinal] of [['shoulderL', 1], ['shoulderR', -1]]) {
      const ombro = this.rig?.[chave];
      const base = ombro?.userData?.baseQuat;
      const eixo = ombro?.userData?.eixoBalanco;
      if (!base || !eixo) continue;
      this._giro.setFromAxisAngle(eixo, balanco * sinal);
      ombro.quaternion.copy(base).multiply(this._giro);
    }
  }

  // Botões coloridos do modelo (os "LEDs" do BMO).
  _collectLeds(model) {
    const leds = [];
    for (const nome of LED_NODES) {
      const obj = porNome(model, nome);
      const mesh = primeiroMesh(obj);
      if (!mesh) continue;
      // O "NurbsPath.002" divide o material com os traços azuis do visor
      // ("Cube.002"/"Cube.003"). Copiar o material deixa a cor do LED só no
      // botão: senão acender o LED vermelho pintaria os olhos do BMO.
      const mats = materiaisDe(mesh);
      if (mats.length === 1) {
        mesh.material = mats[0].clone();
      } else if (mats.length > 1) {
        mesh.material = mats.map((m) => m.clone());
      }
      leds.push(mesh);
    }
    return leds;
  }

  // Troca a textura do rosto do modelo real.
  setFace(url) {
    const rosto = this.rig?.rosto;
    if (!rosto) return false;
    // Só a última chamada vale: se duas texturas chegarem fora de ordem, a
    // mais antiga é descartada para o rosto não ficar com a expressão velha.
    this._faceToken += 1;
    const token = this._faceToken;
    const loader = new THREE.TextureLoader();
    loader.load(url, (tex) => {
      if (token !== this._faceToken) {
        tex.dispose();
        return;
      }
      // glTF usa origem no canto superior: sem flipY a imagem sai de cabeça
      // para baixo (é o que o GLTFLoader faz com as texturas embutidas).
      tex.flipY = false;
      tex.colorSpace = THREE.SRGBColorSpace;
      const mats = Array.isArray(rosto.material) ? rosto.material : [rosto.material];
      // A mesma textura pode estar em mais de um slot do material: junta as
      // texturas antigas num conjunto para descartar cada uma uma vez só.
      const antigas = new Set();
      for (const m of mats) {
        if (m?.map && m.map !== tex) antigas.add(m.map);
      }
      for (const antiga of antigas) antiga.dispose();
      for (const m of mats) {
        if (!m) continue;
        m.map = tex;
        m.needsUpdate = true;
      }
    });
    return true;
  }

  setEmotion(e) {
    if (!EMOTIONS.includes(e)) return;
    // A emoção já é a atual: não recarrega a textura do rosto à toa.
    if (this.emotion === e) return;
    this.emotion = e;
    // O "surpreso" perde força com o tempo, e o decaimento conta a partir
    // da mudança de expressão (não do começo da sessão).
    this._emotionSince = this._t;
    if (this.model) this.setFace(FACES[e]);
  }

  setState(s) {
    this.state = s;
  }

  // Toca uma animação: o BMO inteiro se mexe por "duracao" segundos. Devolve
  // false quando o nome não é uma animação conhecida.
  playAnimation(nome, duracao = 1.5) {
    if (!ANIMACOES.includes(nome)) return false;
    // Duração estranha (NaN, texto) viraria uma transformação NaN e sumiria
    // com o BMO da tela: nesses casos vale a duração padrão.
    const tempo = Number.isFinite(duracao) ? Math.max(0.1, duracao) : 1.5;
    this._animation = { nome, inicio: this._t, duracao: tempo };
    return true;
  }

  // Corta a animação no meio: o BMO volta ao repouso na hora.
  stopAnimation() {
    this._animation = null;
  }

  // Acende os botões do BMO com a cor pedida. Com "piscar", o LED fica
  // piscando enquanto essa cor estiver valendo.
  // A cor é guardada mesmo sem nenhuma malha de LED (o modelo ainda não
  // carregou): ela é repintada assim que o GLB chega.
  setLed(cor, piscar = false) {
    this.ledColor = cor;
    this._ledPiscar = Boolean(piscar);
    for (const led of this.leds ?? []) {
      for (const mat of materiaisDe(led)) {
        mat.color?.set(cor);
        mat.emissive?.set(cor);
        mat.emissiveIntensity = 0.6;
      }
    }
    this._aplicarLed(this._t);
    return true;
  }

  update(dt, mouthOpen) {
    this._t += dt;
    const t = this._t;
    // Com o modelo real carregado o rosto é o do GLB: o canvas procedural
    // fica escondido e não precisa mais ser desenhado.
    if (this.face && this._procedural.visible) this._drawFace(mouthOpen);
    this._applyPose(t);
    this._applyBody(t);
  }

  _applyBody(t) {
    const g = this.group;
    // Cada quadro recomeça do repouso: sem isso a pose de um quadro vazaria
    // para o seguinte (o "bravo" empurrava o corpo para o lado para sempre).
    g.position.set(0, 0, 0);
    g.rotation.set(0, 0, 0);
    g.scale.setScalar(1);
    g.position.y = Math.sin(t * 2) * 0.04;
    // "pensando" tem prioridade sobre a pose da expressão: enquanto o BMO
    // pensa, ele balança no lugar em vez de fazer a cara da emoção. É o
    // comportamento de sempre (o código antigo também pulava a expressão
    // nesse estado) e fica de propósito: a expressão continua guardada e
    // volta quando o estado deixa de ser "pensando".
    if (this.state === 'pensando') {
      g.rotation.z = Math.sin(t * 3) * 0.05;
    } else {
      switch (this.emotion) {
        case 'feliz': g.position.y = Math.abs(Math.sin(t * 4)) * 0.35; break;
        case 'triste': g.rotation.z = -0.12; g.position.y = Math.sin(t * 1.5) * 0.03 - 0.05; break;
        case 'surpreso': {
          // O susto passa com o tempo: o decaimento conta a partir da
          // mudança de expressão, não do começo da sessão.
          const dtEmocao = t - this._emotionSince;
          const s = 1 + 0.15 * Math.sin(t * 10) * Math.exp(-dtEmocao * 0.5);
          g.scale.setScalar(Math.max(1, s));
          break;
        }
        case 'curioso': g.rotation.z = Math.sin(t * 3) * 0.14; break;
        case 'bravo': g.rotation.z = Math.sin(t * 24) * 0.04; g.position.x = Math.sin(t * 24) * 0.02; break;
      }
    }

    // A animação pedida pelo modelo vem por cima da expressão.
    if (this._animation) {
      const k = (t - this._animation.inicio) / this._animation.duracao;
      if (k >= 1) {
        this._animation = null; // acabou sozinha
      } else {
        this._aplicarAnimacao(this._animation.nome, t, k);
      }
    }

    this._aplicarLed(t);
  }

  // Efeito de cada animação, por cima da pose do corpo. "k" é o quanto da
  // animação já passou (0 no começo, 1 no fim).
  _aplicarAnimacao(nome, t, k) {
    const g = this.group;
    switch (nome) {
      case 'pular':
        g.position.y += Math.abs(Math.sin(k * Math.PI * 3)) * 0.35;
        break;
      case 'dancar':
        g.rotation.z = Math.sin(t * 8) * 0.12;
        g.position.y += Math.abs(Math.sin(t * 6)) * 0.1;
        break;
      case 'tremer':
        g.position.x = Math.sin(t * 30) * 0.05;
        g.rotation.z = Math.sin(t * 30) * 0.03;
        break;
      case 'acenar':
        g.rotation.z = Math.sin(t * 10) * 0.18;
        break;
      case 'olhar_lado':
        g.rotation.y = Math.sin(t * 4) * 0.4;
        break;
      case 'dormir':
        g.rotation.z = -0.08;
        g.position.y -= 0.05;
        break;
    }
  }

  // Brilho do LED: piscando, ele alterna entre fraco e forte; parado, fica
  // no brilho normal.
  _aplicarLed(t) {
    if (!this.ledColor) return;
    const leds = this.leds ?? [];
    if (!leds.length) return;
    const brilho = this._ledPiscar ? (Math.sin(t * 10) > 0 ? 1.0 : 0.2) : 0.6;
    for (const led of leds) {
      for (const mat of materiaisDe(led)) {
        mat.emissiveIntensity = brilho;
      }
    }
  }

  _drawFace(mouth) {
    const c = this.ctx;
    const W = this.canvas.width;
    const cx = W / 2;
    const eyeY = 100;
    const mouthY = 158;
    c.clearRect(0, 0, W, this.canvas.height);
    c.fillStyle = '#eafff0';
    c.strokeStyle = '#eafff0';
    c.lineCap = 'round';

    const state = this.state;
    const e = this.emotion;
    const r = 18;

    if (state === 'pensando') {
      for (let i = -1; i <= 1; i++) { c.beginPath(); c.arc(cx + i * 40, eyeY, 10, 0, Math.PI * 2); c.fill(); }
    } else if (e === 'feliz') {
      c.lineWidth = 8;
      for (const sx of [-45, 45]) { c.beginPath(); c.arc(cx + sx, eyeY + 12, 20, Math.PI * 1.1, Math.PI * 1.9); c.stroke(); }
    } else if (e === 'triste') {
      c.lineWidth = 8;
      for (const sx of [-45, 45]) { c.beginPath(); c.arc(cx + sx, eyeY - 8, 18, Math.PI * 0.1, Math.PI * 0.9); c.stroke(); }
    } else if (e === 'surpreso') {
      for (const sx of [-45, 45]) { c.beginPath(); c.arc(cx + sx, eyeY, r + 4, 0, Math.PI * 2); c.fill(); }
    } else if (e === 'bravo') {
      for (const sx of [-45, 45]) { c.beginPath(); c.arc(cx + sx, eyeY, r, 0, Math.PI * 2); c.fill(); }
      c.lineWidth = 8;
      c.beginPath(); c.moveTo(cx - 45 - 16, eyeY - 34); c.lineTo(cx - 45 + 16, eyeY - 14);
      c.moveTo(cx + 45 + 16, eyeY - 34); c.lineTo(cx + 45 - 16, eyeY - 14); c.stroke();
    } else {
      for (const sx of [-45, 45]) { c.beginPath(); c.arc(cx + sx, eyeY, r, 0, Math.PI * 2); c.fill(); }
    }

    const open = Math.max(0, Math.min(1, mouth));

    if (state === 'pensando') {
      c.beginPath(); c.arc(cx, mouthY, 8, 0, Math.PI * 2); c.fill();
    } else if (e === 'feliz') {
      c.beginPath(); c.arc(cx, mouthY - 6, 32, 0.15 * Math.PI, 0.85 * Math.PI); c.fill();
    } else if (e === 'triste') {
      c.lineWidth = 8;
      c.beginPath(); c.arc(cx, mouthY + 24, 24, 1.15 * Math.PI, 1.85 * Math.PI); c.stroke();
    } else if (e === 'surpreso') {
      c.beginPath(); c.arc(cx, mouthY, 12 + 8 * open, 0, Math.PI * 2); c.fill();
    } else if (e === 'bravo') {
      c.lineWidth = 8;
      c.beginPath(); c.moveTo(cx - 20, mouthY + 8); c.lineTo(cx + 20, mouthY - 4); c.stroke();
    } else {
      const h = open > 0.02 ? 6 + 18 * open : 5;
      c.beginPath(); c.ellipse(cx, mouthY, 16, h, 0, 0, Math.PI * 2); c.fill();
    }

    this.tex.needsUpdate = true;
  }
}
