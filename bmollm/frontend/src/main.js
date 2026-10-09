import * as THREE from 'three';
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
const ws = new WSClient({
  onJson: (msg) => handleJson(msg),
  onBinary: (buf) => audio.playChunk(buf),
  onOpen: () => ui.setEstado('pronto — segure para falar'),
  onClose: () => ui.setEstado('desconectado'),
});

function handleJson(msg) {
  switch (msg.type) {
    case 'transcricao': ui.setTranscript('ouvi: ' + msg.texto); break;
    case 'estado':
      ui.setEstado(msg.estado);
      if (msg.estado === 'pensando') bmo.setState('pensando');
      break;
    case 'emocao': bmo.setEmotion(msg.emocao); ui.setEmocao(msg.emocao); break;
    case 'frase': ui.setFrase(msg.texto); break;
    case 'audio_meta': audio.resetPlayback(); break;
    case 'audio_fim': ui.setEstado('pronto'); bmo.setState('pronto'); break;
    case 'parar': audio.stop(); bmo.setState('pronto'); ui.setEstado('pronto'); break;
    case 'erro': ui.setErro(msg.mensagem); ui.setEstado('pronto'); bmo.setState('pronto'); break;
  }
}

ui.onTalkStart = () => audio.startRecording();
ui.onTalkEnd = async () => {
  const buf = await audio.stopRecording();
  if (buf) ws.sendAudio(buf);
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
