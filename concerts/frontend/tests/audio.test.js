import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AudioManager } from '../src/audio.js';

// Dublê do Web Audio: só o que o AudioManager usa. Sem ele o teste depende
// de placa de som e de microfone de verdade.
class FakeSource {
  connect() {}
  start(t) { this.started = t; }
  stop() { this.stopped = true; }
}

class FakeCtx {
  constructor() {
    this.currentTime = 0;
    this.destination = {};
    this.state = 'running';
    this.sources = [];
  }
  createAnalyser() {
    return {
      fftSize: 256,
      frequencyBinCount: 128,
      connect() {},
      getByteTimeDomainData(buf) { buf.fill(128); },
    };
  }
  createBuffer(_channels, length, rate) {
    const data = new Float32Array(length);
    return { duration: length / rate, getChannelData: () => data };
  }
  createBufferSource() {
    const source = new FakeSource();
    this.sources.push(source);
    return source;
  }
  createOscillator() {
    return {
      type: '',
      frequency: { value: 0 },
      connect() {},
      start() { this.started = true; },
      stop() { this.stopped = true; },
    };
  }
  createGain() {
    return { gain: { value: 0 }, connect() {} };
  }
  resume() {}
}

describe('AudioManager', () => {
  beforeEach(() => vi.stubGlobal('AudioContext', FakeCtx));
  afterEach(() => vi.unstubAllGlobals());

  it('agenda chunks em sequência e limpa ao parar', () => {
    const audio = new AudioManager();
    audio.playChunk(new Int16Array(24000).buffer);
    audio.playChunk(new Int16Array(12000).buffer);

    const [primeira, segunda] = audio._sources;
    expect(primeira.started).toBe(0);
    expect(segunda.started).toBeCloseTo(1.0);

    audio.stop();
    expect(audio._sources).toEqual([]);
    expect(audio._nextTime).toBe(0);
  });

  it('remove a fonte quando o áudio termina', () => {
    const audio = new AudioManager();
    audio.playChunk(new Int16Array(10).buffer);
    const fonte = audio._sources[0];

    fonte.onended();

    expect(audio._sources).toEqual([]);
  });

  it('toca beep sem quebrar', () => {
    const audio = new AudioManager();
    expect(() => audio.playBeep('bip')).not.toThrow();
  });
});
