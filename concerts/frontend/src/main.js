import * as THREE from 'three';
import { ActionDispatcher } from './actions.js';
import { Bmo } from './bmo.js';
import { AudioManager } from './audio.js';
import { WSClient } from './ws.js';
import { UI } from './ui.js';

const sceneEl = document.getElementById('scene');

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
camera.position.set(0, 0.6, 4.5);
camera.lookAt(0, 0.2, 0);

const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
sceneEl.appendChild(renderer.domElement);

const hemi = new THREE.HemisphereLight(0xffffff, 0x223344, 1.2);
scene.add(hemi);
const dir = new THREE.DirectionalLight(0xffffff, 1.6);
dir.position.set(2, 4, 3);
scene.add(dir);

const bmo = new Bmo();
scene.add(bmo.group);

const ui = new UI();
const audio = new AudioManager();
audio.onError = (msg) => {
  ui.cancelRecording();
  ui.setErro(msg);
  ui.setEstado('sem microfone');
};

// As ações que o modelo pede chegam pelo WebSocket e são executadas aqui,
// no BMO da tela. A allowlist fica no dispatcher: nome desconhecido é
// ignorado, nunca vira chamada de código.
const actions = new ActionDispatcher({ bmo, ui, audio });

// O botão precisa dizer o que o BMO está fazendo enquanto processa.
// Se o backend não responder a tempo, a tela volta ao normal — um Ollama
// travado não pode congelar a feira.
const TIMEOUT_RESPOSTA_MS = 12_000;
let timerResposta = null;
let timerSemConexao = null;
let erroTimeout = '';

function armarTimeoutResposta() {
  clearTimeout(timerResposta);
  timerResposta = setTimeout(() => {
    timerResposta = null;
    erroTimeout = 'O BMO não respondeu. Tenta de novo.';
    ui.setBotao('idle');
    ui.setEstado('sem resposta do BMO');
    ui.setErro(erroTimeout);
  }, TIMEOUT_RESPOSTA_MS);
}

// Cancela a espera e limpa a mensagem de timeout (resposta atrasada).
function cancelarTimeoutResposta() {
  if (timerResposta) { clearTimeout(timerResposta); timerResposta = null; }
  if (erroTimeout) { erroTimeout = ''; ui.setErro(''); }
}

// Sem conexão o botão avisa e volta ao normal depois de um tempo.
function avisarSemConexao() {
  ui.setBotao('sem-conexao');
  ui.setErro('Sem conexão com o servidor. Tentando reconectar…');
  clearTimeout(timerSemConexao);
  timerSemConexao = setTimeout(() => {
    timerSemConexao = null;
    ui.setBotao('idle');
    ui.setErro('');
  }, 3000);
}

const ws = new WSClient({
  onJson: (msg) => handleJson(msg),
  onBinary: (buf) => audio.playChunk(buf),
  onOpen: () => {
    ui.setEstado('pronto — segure para falar');
    // A conexão voltou: o botão não precisa mais ficar avisando que está
    // sem conexão.
    if (ui.botaoEstado === 'sem-conexao') {
      clearTimeout(timerSemConexao);
      timerSemConexao = null;
      ui.setBotao('idle');
      ui.setErro('');
    }
  },
  onClose: () => {
    ui.setEstado('desconectado');
    // Caiu a conexão no meio de uma resposta: sem 'audio_fim' o botão ficaria
    // preso em "Pensando…" ou "Falando…".
    if (['esperando', 'pensando', 'falando'].includes(ui.botaoEstado)) avisarSemConexao();
  },
});

// Gancho de teste: só existe com ?e2e=1 na URL, então a produção não muda.
const e2e = new URLSearchParams(location.search).has('e2e');
if (e2e) {
  window.__bmoTest = {
    bmo,
    ui,
    audio,
    ws,
    lastJson: null,
    actions: [],
    send(token) { ws.sendAudio(new TextEncoder().encode(token)); },
    closeSocket() { ws.ws?.close(); },
  };
}

function handleJson(msg) {
  if (window.__bmoTest) window.__bmoTest.lastJson = msg;
  // 'parar' só avisa que a resposta anterior foi cortada: a nova ainda está a
  // caminho, então o prazo de espera da resposta continua valendo.
  if (msg.type !== 'parar') cancelarTimeoutResposta();
  switch (msg.type) {
    case 'transcricao': ui.setTranscript('ouvi: ' + msg.texto); ui.setBotao('pensando'); break;
    case 'estado':
      ui.setEstado(msg.estado);
      if (msg.estado === 'pensando') bmo.setState('pensando');
      break;
    case 'emocao': bmo.setEmotion(msg.emocao); ui.setEmocao(msg.emocao); break;
    case 'acao':
      // O gancho de teste guarda as ações recebidas para o E2E olhar.
      window.__bmoTest?.actions.push(msg);
      actions.execute(msg);
      break;
    case 'frase': ui.setFrase(msg.texto); ui.setBotao('falando'); break;
    case 'audio_meta': audio.resetPlayback(); break;
    case 'audio_fim': ui.setEstado('pronto'); bmo.setState('pronto'); ui.setBotao('idle'); break;
    case 'parar':
      audio.stop();
      bmo.stopAnimation();
      bmo.setState('pronto');
      // Enquanto o botão está sendo segurado o estado é 'gravando': o 'parar'
      // não pode tirar o botão desse estado, senão o pointerup não solta a
      // gravação e o microfone fica aberto.
      if (ui.botaoEstado !== 'gravando') {
        ui.setEstado('pronto');
        ui.setBotao('idle');
      }
      break;
    case 'erro': ui.setErro(msg.mensagem); ui.setEstado('pronto'); bmo.setState('pronto'); ui.setBotao('idle'); break;
  }
}

ui.onTalkStart = () => {
  clearTimeout(timerSemConexao);
  timerSemConexao = null;
  ui.setBotao('gravando');
  // Barge-in: o BMO cala na hora quando o botão é apertado de novo. O áudio
  // local é cortado antes de qualquer conversa com o servidor, para o
  // primeiro som não sair nada depois do dedo tocar o botão.
  audio.stop();
  bmo.stopAnimation();
  ws.interrupt();
  audio.startRecording();
};
ui.onTalkEnd = async () => {
  cancelarTimeoutResposta();
  const buf = await audio.stopRecording();
  if (!buf) { ui.setBotao('idle'); return; }
  const enviado = ws.sendAudio(buf);
  if (enviado) {
    ui.setBotao('esperando');
    ui.setEstado('reconhecendo…');
    armarTimeoutResposta();
  } else {
    avisarSemConexao();
    ui.setEstado('desconectado');
  }
};

function resize() {
  const w = window.innerWidth, h = window.innerHeight;
  renderer.setSize(w, h);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
window.addEventListener('resize', resize);
resize();

const clock = new THREE.Clock();
function loop() {
  const dt = clock.getDelta();
  const mouth = Math.min(1, audio.getLevel() * 4);
  bmo.update(dt, mouth);
  renderer.render(scene, camera);
  requestAnimationFrame(loop);
}
loop();

ws.connect();
