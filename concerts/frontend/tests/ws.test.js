import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { WSClient } from '../src/ws.js';

class FakeWebSocket {
  static OPEN = 1;
  static instances = [];

  constructor(url) {
    this.url = url;
    this.readyState = 0;
    this.sent = [];
    FakeWebSocket.instances.push(this);
  }

  send(data) { this.sent.push(data); }
  close() { this.readyState = 3; this.onclose?.(); }
  open() { this.readyState = 1; this.onopen?.(); }
  message(data) { this.onmessage?.({ data }); }
}

describe('WSClient', () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    vi.stubGlobal('WebSocket', FakeWebSocket);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('conecta em /ws e entrega JSON e binário', () => {
    const onJson = vi.fn();
    const onBinary = vi.fn();
    const client = new WSClient({ onJson, onBinary });
    client.connect();

    const socket = FakeWebSocket.instances[0];
    expect(socket.url).toBe('ws://localhost:8000/ws');
    expect(socket.binaryType).toBe('arraybuffer');

    socket.message('{"type":"estado","estado":"pronto"}');
    expect(onJson).toHaveBeenCalledWith({ type: 'estado', estado: 'pronto' });

    const buffer = new ArrayBuffer(4);
    socket.message(buffer);
    expect(onBinary).toHaveBeenCalledWith(buffer);
  });

  it('só envia áudio quando o socket está aberto', () => {
    const client = new WSClient();
    client.connect();
    const socket = FakeWebSocket.instances[0];

    const buffer = new ArrayBuffer(2);
    client.sendAudio(buffer);
    expect(socket.sent).toEqual([]);

    socket.open();
    client.sendAudio(buffer);
    expect(socket.sent).toEqual([buffer]);
  });

  it('sendAudio devolve false quando o socket está fechado', () => {
    const client = new WSClient();
    client.connect();

    expect(client.sendAudio(new ArrayBuffer(2))).toBe(false);
  });

  it('sendAudio devolve true quando o socket está aberto', () => {
    const client = new WSClient();
    client.connect();
    FakeWebSocket.instances[0].open();

    expect(client.sendAudio(new ArrayBuffer(2))).toBe(true);
  });

  it('tenta reconectar 2 s depois de fechar', () => {
    vi.useFakeTimers();
    const client = new WSClient();
    client.connect();
    FakeWebSocket.instances[0].close();

    expect(FakeWebSocket.instances).toHaveLength(1);
    vi.advanceTimersByTime(2000);
    expect(FakeWebSocket.instances).toHaveLength(2);
  });

  it('interrupt envia JSON e sendAudio devolve boolean', () => {
    const client = new WSClient();
    client.connect();
    const socket = FakeWebSocket.instances[0];

    expect(client.sendAudio(new ArrayBuffer(2))).toBe(false);
    expect(client.interrupt()).toBe(false);

    socket.open();
    expect(client.sendAudio(new ArrayBuffer(2))).toBe(true);
    expect(client.interrupt()).toBe(true);
    expect(socket.sent.at(-1)).toBe('{"type":"interromper"}');
  });

  it('isOpen segue o estado do socket', () => {
    const client = new WSClient();

    expect(client.isOpen()).toBe(false);
    client.connect();
    expect(client.isOpen()).toBe(false);

    FakeWebSocket.instances[0].open();
    expect(client.isOpen()).toBe(true);

    FakeWebSocket.instances[0].close();
    expect(client.isOpen()).toBe(false);
  });
});
