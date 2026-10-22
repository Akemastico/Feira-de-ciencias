// Estados possíveis do botão de falar e o que cada um mostra na tela.
const ESTADOS_BOTAO = {
  idle: { texto: 'Segure para falar', classe: '' },
  gravando: { texto: 'Ouvindo…', classe: 'recording' },
  esperando: { texto: 'Reconhecendo…', classe: 'esperando' },
  pensando: { texto: 'Pensando…', classe: 'esperando' },
  falando: { texto: 'Falando…', classe: 'falando' },
  'sem-conexao': { texto: 'Sem conexão', classe: 'erro' },
};

export class UI {
  constructor() {
    this.btn = document.getElementById('btn');
    this.onTalkStart = null;
    this.onTalkEnd = null;
    this.botaoEstado = 'idle';
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

  cancelRecording() {
    this.setBotao('idle');
  }

  // Estado novo do botão: troca o texto, limpa as classes antigas e
  // guarda o estado atual em this.botaoEstado. Estado desconhecido cai em idle.
  setBotao(estado) {
    const nome = ESTADOS_BOTAO[estado] ? estado : 'idle';
    const cfg = ESTADOS_BOTAO[nome];
    this.btn.textContent = cfg.texto;
    this.btn.classList.remove('recording', 'esperando', 'falando', 'erro');
    if (cfg.classe) this.btn.classList.add(cfg.classe);
    this.botaoEstado = nome;
  }

  setEstado(s) { document.getElementById('estado').textContent = s; }
  setFrase(t) { document.getElementById('frase').textContent = t; }
  setTranscript(t) { document.getElementById('transcricao').textContent = t; }
  setErro(m) { document.getElementById('erro').textContent = m; }
  setEmocao(e) { document.getElementById('emocao').textContent = e; }
}
