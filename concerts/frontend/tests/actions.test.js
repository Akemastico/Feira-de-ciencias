import { describe, expect, it, vi } from 'vitest';
import { ActionDispatcher } from '../src/actions.js';

function montar() {
  const bmo = {
    setEmotion: vi.fn(),
    playAnimation: vi.fn(),
    setLed: vi.fn(),
  };
  const ui = { setEmocao: vi.fn(), setFrase: vi.fn() };
  const audio = { playBeep: vi.fn() };
  const log = { warn: vi.fn() };
  return {
    bmo,
    ui,
    audio,
    log,
    dispatcher: new ActionDispatcher({ bmo, ui, audio, log }),
  };
}

describe('ActionDispatcher', () => {
  it('executa expressao, animacao, texto, led e som', () => {
    const { dispatcher, bmo, ui, audio } = montar();

    expect(dispatcher.execute({ nome: 'expressao', args: { emocao: 'feliz' } })).toBe(true);
    expect(bmo.setEmotion).toHaveBeenCalledWith('feliz');
    expect(ui.setEmocao).toHaveBeenCalledWith('feliz');

    expect(dispatcher.execute({ nome: 'animacao', args: { nome: 'pular', duracao: 1.2 } })).toBe(true);
    expect(bmo.playAnimation).toHaveBeenCalledWith('pular', 1.2);

    expect(dispatcher.execute({ nome: 'texto', args: { texto: 'Oi!' } })).toBe(true);
    expect(ui.setFrase).toHaveBeenCalledWith('Oi!');

    expect(dispatcher.execute({ nome: 'led', args: { cor: '#ff0000' } })).toBe(true);
    expect(bmo.setLed).toHaveBeenCalledWith('#ff0000', false);

    expect(dispatcher.execute({ nome: 'som', args: { tipo: 'bip' } })).toBe(true);
    expect(audio.playBeep).toHaveBeenCalledWith('bip');
  });

  it('ignora ação desconhecida e argumentos inválidos', () => {
    const { dispatcher, bmo, log } = montar();

    expect(dispatcher.execute({ nome: 'hackear', args: {} })).toBe(false);
    expect(dispatcher.execute({ nome: 'animacao', args: { nome: 'voar' } })).toBe(false);
    expect(bmo.playAnimation).not.toHaveBeenCalled();
    expect(log.warn).toHaveBeenCalled();
  });

  it('não para o lote quando um handler lança erro', () => {
    const { dispatcher, bmo, ui, log } = montar();
    bmo.playAnimation.mockImplementation(() => { throw new Error('boom'); });

    const executadas = dispatcher.executeAll([
      { nome: 'animacao', args: { nome: 'pular' } },
      { nome: 'texto', args: { texto: 'Oi!' } },
    ]);

    expect(executadas).toBe(1);
    expect(ui.setFrase).toHaveBeenCalledWith('Oi!');
    expect(log.warn).toHaveBeenCalled();
  });

  it('trata mensagem sem nome/args como inválida', () => {
    const { dispatcher } = montar();

    expect(dispatcher.execute({})).toBe(false);
    expect(dispatcher.execute({ nome: 'som' })).toBe(false);
  });

  it('ignora ação cujo método ainda não existe no BMO', () => {
    const { dispatcher, bmo, log } = montar();
    // playAnimation/setLed/playBeep chegam depois: enquanto isso a ação é
    // ignorada com aviso, sem estourar erro na tela.
    delete bmo.playAnimation;

    expect(() => dispatcher.execute({ nome: 'animacao', args: { nome: 'pular' } })).not.toThrow();
    expect(dispatcher.execute({ nome: 'animacao', args: { nome: 'pular' } })).toBe(false);
    expect(log.warn).toHaveBeenCalled();
  });

  it('executeAll devolve zero quando a lista de ações não é uma lista', () => {
    const { dispatcher } = montar();

    expect(dispatcher.executeAll(null)).toBe(0);
    expect(dispatcher.executeAll({ nome: 'som', args: { tipo: 'bip' } })).toBe(0);
  });
});
