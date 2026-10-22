export class AudioManager {
  constructor() {
    this.ctx = null;
    this.stream = null;
    this.recorder = null;
    this.chunks = [];
    this._nextTime = 0;
    this._sources = [];
    this._analyser = null;
    this._data = null;
    this.onError = () => {};
  }

  _ensureCtx() {
    if (!this.ctx) {
      this.ctx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });
      this._analyser = this.ctx.createAnalyser();
      this._analyser.fftSize = 256;
      this._analyser.connect(this.ctx.destination);
      this._data = new Uint8Array(this._analyser.frequencyBinCount);
    }
    if (this.ctx.state === 'suspended') this.ctx.resume();
    return this.ctx;
  }

  async startRecording() {
    try {
      this._ensureCtx();
      if (!this.stream) this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      this.chunks = [];
      const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : '';
      this.recorder = mime ? new MediaRecorder(this.stream, { mimeType: mime }) : new MediaRecorder(this.stream);
      this.recorder.ondataavailable = (e) => { if (e.data.size > 0) this.chunks.push(e.data); };
      this.recorder.start();
      return true;
    } catch (err) {
      console.error('Falha ao gravar:', err);
      this.onError(this._mensagem(err));
      return false;
    }
  }

  _mensagem(err) {
    const nome = err && err.name;
    if (nome === 'NotAllowedError' || nome === 'SecurityError') {
      return 'Microfone bloqueado. Clique no cadeado do navegador e permita o microfone.';
    }
    if (nome === 'NotFoundError' || nome === 'OverconstrainedError') {
      return 'Nenhum microfone encontrado. Confere se ele está conectado.';
    }
    return 'Não consegui usar o microfone: ' + (err && err.message ? err.message : err);
  }

  async stopRecording() {
    if (!this.recorder || this.recorder.state === 'inactive') return null;
    return new Promise((resolve) => {
      this.recorder.onstop = () => {
        const blob = new Blob(this.chunks, { type: this.recorder.mimeType || 'audio/webm' });
        blob.arrayBuffer().then(resolve);
      };
      this.recorder.stop();
    });
  }

  resetPlayback() {
    this._nextTime = 0;
  }

  playChunk(pcm) {
    const ctx = this._ensureCtx();
    const int16 = new Int16Array(pcm);
    const f32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) f32[i] = int16[i] / 32768;
    const buf = ctx.createBuffer(1, f32.length, 24000);
    buf.getChannelData(0).set(f32);
    const src = ctx.createBufferSource();
    src.buffer = buf;
    src.connect(this._analyser);
    const now = ctx.currentTime;
    if (this._nextTime < now) this._nextTime = now;
    src.start(this._nextTime);
    this._sources.push(src);
    // A fonte sai da lista quando o áudio acaba: numa apresentação longa a
    // lista não pode crescer sem parar.
    src.onended = () => {
      this._sources = this._sources.filter((s) => s !== src);
    };
    this._nextTime += buf.duration;
  }

  // Bip do BMO: som curtinho que confirma que a ação do modelo aconteceu.
  // "erro" e "sucesso" são tons diferentes do bip normal.
  playBeep(tipo = 'bip') {
    try {
      const ctx = this._ensureCtx();
      const freq = { bip: 880, erro: 220, sucesso: 1320 }[tipo] || 880;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.value = freq;
      gain.gain.value = 0.05;
      osc.connect(gain);
      gain.connect(ctx.destination);
      const now = ctx.currentTime;
      osc.start(now);
      osc.stop(now + 0.12);
    } catch (err) {
      console.warn('Não consegui tocar o som:', err);
    }
  }

  stop() {
    for (const s of this._sources) { try { s.stop(); } catch (e) {} }
    this._sources = [];
    this._nextTime = 0;
  }

  getLevel() {
    if (!this._analyser) return 0;
    this._analyser.getByteTimeDomainData(this._data);
    let sum = 0;
    for (let i = 0; i < this._data.length; i++) {
      const v = (this._data[i] - 128) / 128;
      sum += v * v;
    }
    return Math.sqrt(sum / this._data.length);
  }
}
