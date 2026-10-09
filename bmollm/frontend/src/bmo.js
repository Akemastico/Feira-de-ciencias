import * as THREE from 'three';
import { GLTFLoader } from '/vendor/three/GLTFLoader.js';

const EMOTIONS = ['neutro', 'feliz', 'triste', 'surpreso', 'curioso', 'bravo'];

export class Bmo {
  constructor() {
    this.group = new THREE.Group();
    this.emotion = 'neutro';
    this.state = 'pronto';
    this._t = 0;
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
    const b2 = b1.clone();
    b2.position.y = -0.12;
    const b3 = new THREE.Mesh(
      new THREE.BoxGeometry(0.1, 0.08, 0.06),
      new THREE.MeshStandardMaterial({ color: 0xe05555 })
    );
    b3.position.set(-0.51, 0.42, 0.15);

    this.group.add(this.body, this.screen, this.face, b1, b2, b3);
  }

  _tryLoadGlb() {
    const loader = new GLTFLoader();
    loader.load(
      '/assets/bmo.glb',
      (gltf) => {
        const model = gltf.scene;
        const box = new THREE.Box3().setFromObject(model);
        const size = box.getSize(new THREE.Vector3());
        const maxDim = Math.max(size.x, size.y, size.z) || 1;
        const s = 1.6 / maxDim;
        model.scale.setScalar(s);
        const center = box.getCenter(new THREE.Vector3());
        model.position.sub(center.multiplyScalar(s));
        model.position.y += 0.2;
        if (this.body) {
          this.group.remove(this.body);
          this.body = null;
        }
        this.group.add(model);
      },
      undefined,
      () => { /* GLB ausente — mantém o BMO procedural */ }
    );
  }

  setEmotion(e) {
    if (EMOTIONS.includes(e)) this.emotion = e;
  }

  setState(s) {
    this.state = s;
  }

  update(dt, mouthOpen) {
    this._t += dt;
    const t = this._t;
    this._drawFace(mouthOpen);
    this._applyBody(t);
  }

  _applyBody(t) {
    const g = this.group;
    g.rotation.z = 0;
    g.rotation.x = 0;
    g.scale.setScalar(1);
    g.position.y = Math.sin(t * 2) * 0.04;
    if (this.state === 'pensando') {
      g.rotation.z = Math.sin(t * 3) * 0.05;
      return;
    }
    switch (this.emotion) {
      case 'feliz': g.position.y = Math.abs(Math.sin(t * 4)) * 0.35; break;
      case 'triste': g.rotation.z = -0.12; g.position.y = Math.sin(t * 1.5) * 0.03 - 0.05; break;
      case 'surpreso': {
        const s = 1 + 0.15 * Math.sin(t * 10) * Math.exp(-t * 0.5);
        g.scale.setScalar(Math.max(1, s));
        break;
      }
      case 'curioso': g.rotation.z = Math.sin(t * 3) * 0.14; break;
      case 'bravo': g.rotation.z = Math.sin(t * 24) * 0.04; g.position.x = Math.sin(t * 24) * 0.02; break;
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
