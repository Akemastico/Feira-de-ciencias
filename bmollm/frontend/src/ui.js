export class UI {
  constructor() {
    this.btn = document.getElementById('btn');
    this.onTalkStart = null;
    this.onTalkEnd = null;
    this._bind();
  }

  _bind() {
    const start = (e) => {
      e.preventDefault();
      if (this.btn.classList.contains('recording')) return;
      this.btn.classList.add('recording');
      if (this.onTalkStart) this.onTalkStart();
    };
    const end = () => {
      if (!this.btn.classList.contains('recording')) return;
      this.btn.classList.remove('recording');
      if (this.onTalkEnd) this.onTalkEnd();
    };
    this.btn.addEventListener('pointerdown', start);
    this.btn.addEventListener('pointerup', end);
    this.btn.addEventListener('pointerleave', end);
    window.addEventListener('keydown', (e) => { if (e.code === 'Space' && !e.repeat) start(e); });
    window.addEventListener('keyup', (e) => { if (e.code === 'Space') end(); });
  }

  setEstado(s) { document.getElementById('estado').textContent = s; }
  setFrase(t) { document.getElementById('frase').textContent = t; }
  setTranscript(t) { document.getElementById('transcricao').textContent = t; }
  setErro(m) { document.getElementById('erro').textContent = m; }
  setEmocao(e) { document.getElementById('emocao').textContent = e; }
}
