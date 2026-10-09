export class WSClient {
  constructor({ onJson, onBinary, onOpen, onClose } = {}) {
    this.onJson = onJson || (() => {});
    this.onBinary = onBinary || (() => {});
    this.onOpen = onOpen || (() => {});
    this.onClose = onClose || (() => {});
    this.ws = null;
  }

  connect() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    this.ws = new WebSocket(`${proto}://${location.host}/ws`);
    this.ws.binaryType = 'arraybuffer';
    this.ws.onopen = () => this.onOpen();
    this.ws.onmessage = (ev) => {
      if (typeof ev.data === 'string') this.onJson(JSON.parse(ev.data));
      else this.onBinary(ev.data);
    };
    this.ws.onclose = () => {
      this.onClose();
      setTimeout(() => this.connect(), 2000);
    };
  }

  sendAudio(buf) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) this.ws.send(buf);
  }
}
