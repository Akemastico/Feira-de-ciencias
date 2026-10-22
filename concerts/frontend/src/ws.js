export class WSClient {
  constructor({ onJson, onBinary, onOpen, onClose } = {}) {
    this.onJson = onJson || (() => {});
    this.onBinary = onBinary || (() => {});
    this.onOpen = onOpen || (() => {});
    this.onClose = onClose || (() => {});
    this.ws = null;
    this._retry = null;
  }

  connect() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    this.ws = new WebSocket(`${proto}://${location.host}/ws`);
    this.ws.binaryType = 'arraybuffer';
    this.ws.onopen = () => {
      if (this._retry) { clearTimeout(this._retry); this._retry = null; }
      this.onOpen();
    };
    this.ws.onmessage = (ev) => {
      if (typeof ev.data !== 'string') { this.onBinary(ev.data); return; }
      try {
        this.onJson(JSON.parse(ev.data));
      } catch (err) {
        console.error('Mensagem inválida do servidor:', ev.data, err);
      }
    };
    this.ws.onclose = () => {
      this.onClose();
      if (!this._retry) {
        this._retry = setTimeout(() => { this._retry = null; this.connect(); }, 2000);
      }
    };
  }

  // O socket está pronto para mandar mensagem?
  isOpen() {
    return Boolean(this.ws && this.ws.readyState === WebSocket.OPEN);
  }

  // Devolve true quando o áudio saiu, false quando não há socket aberto —
  // assim a interface consegue avisar que está sem conexão.
  sendAudio(buf) {
    if (!this.isOpen()) return false;
    this.ws.send(buf);
    return true;
  }

  // Barge-in: avisa o servidor que o usuário apertou o botão de novo e quer
  // o BMO calado agora, sem esperar o áudio novo chegar.
  interrupt() {
    if (!this.isOpen()) return false;
    this.ws.send(JSON.stringify({ type: 'interromper' }));
    return true;
  }
}
