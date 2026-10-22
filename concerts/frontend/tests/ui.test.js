import { beforeEach, describe, expect, it } from 'vitest';
import { UI } from '../src/ui.js';

function montarTela() {
  document.body.innerHTML = `
    <div id="emocao"></div>
    <div id="estado"></div>
    <div id="frase"></div>
    <div id="transcricao"></div>
    <div id="erro"></div>
    <button id="btn">Segure para falar</button>
  `;
}

describe('UI.setBotao', () => {
  beforeEach(() => {
    montarTela();
  });

  it('começa ocioso, com o texto e a classe de espera', () => {
    const ui = new UI();

    expect(ui.botaoEstado).toBe('idle');
    expect(ui.btn.textContent).toBe('Segure para falar');
    expect(ui.btn.classList.contains('esperando')).toBe(false);
  });

  it('troca o texto e a classe conforme o estado', () => {
    const ui = new UI();

    ui.setBotao('gravando');
    expect(ui.botaoEstado).toBe('gravando');
    expect(ui.btn.textContent).toBe('Ouvindo…');
    expect(ui.btn.classList.contains('recording')).toBe(true);

    ui.setBotao('esperando');
    expect(ui.botaoEstado).toBe('esperando');
    expect(ui.btn.textContent).toBe('Reconhecendo…');
    expect(ui.btn.classList.contains('esperando')).toBe(true);
    expect(ui.btn.classList.contains('recording')).toBe(false);

    ui.setBotao('pensando');
    expect(ui.botaoEstado).toBe('pensando');
    expect(ui.btn.textContent).toBe('Pensando…');
    expect(ui.btn.classList.contains('esperando')).toBe(true);

    ui.setBotao('falando');
    expect(ui.botaoEstado).toBe('falando');
    expect(ui.btn.textContent).toBe('Falando…');
    expect(ui.btn.classList.contains('falando')).toBe(true);
    expect(ui.btn.classList.contains('esperando')).toBe(false);

    ui.setBotao('sem-conexao');
    expect(ui.botaoEstado).toBe('sem-conexao');
    expect(ui.btn.textContent).toBe('Sem conexão');
    expect(ui.btn.classList.contains('erro')).toBe(true);
    expect(ui.btn.classList.contains('falando')).toBe(false);
  });

  it('voltar para idle limpa as classes', () => {
    const ui = new UI();
    ui.setBotao('falando');

    ui.setBotao('idle');

    expect(ui.botaoEstado).toBe('idle');
    expect(ui.btn.textContent).toBe('Segure para falar');
    for (const classe of ['recording', 'esperando', 'falando', 'erro']) {
      expect(ui.btn.classList.contains(classe)).toBe(false);
    }
  });

  it('estado desconhecido cai em idle', () => {
    const ui = new UI();
    ui.setBotao('falando');

    ui.setBotao('estado-que-nao-existe');

    expect(ui.botaoEstado).toBe('idle');
    expect(ui.btn.textContent).toBe('Segure para falar');
    expect(ui.btn.classList.contains('falando')).toBe(false);
  });
});

describe('UI e o botão do microfone', () => {
  beforeEach(() => {
    montarTela();
  });

  it('cancelRecording devolve o botão ao estado ocioso', () => {
    const ui = new UI();
    ui.setBotao('gravando');

    ui.cancelRecording();

    expect(ui.botaoEstado).toBe('idle');
    expect(ui.btn.textContent).toBe('Segure para falar');
    expect(ui.btn.classList.contains('recording')).toBe(false);
  });

  it('apertar e soltar o botão dispara onTalkStart e onTalkEnd', () => {
    const ui = new UI();
    let started = 0;
    let ended = 0;
    ui.onTalkStart = () => { started += 1; };
    ui.onTalkEnd = () => { ended += 1; };

    ui.btn.dispatchEvent(new Event('pointerdown'));
    ui.btn.dispatchEvent(new Event('pointerup'));

    expect(started).toBe(1);
    expect(ended).toBe(1);
  });
});
