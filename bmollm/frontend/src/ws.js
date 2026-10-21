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

  sendAudio(buf) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) this.ws.send(buf);
  }
}
