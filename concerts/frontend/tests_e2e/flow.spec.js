import { expect, test } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.goto('/?e2e=1');
  await expect(page.locator('#estado')).toContainText('pronto');
});

test('resposta ok atualiza transcrição, emoção, frase e volta a pronto', async ({ page }) => {
  await page.evaluate(() => window.__bmoTest.send('ok'));

  await expect(page.locator('#transcricao')).toHaveText('ouvi: oi bmo');
  await expect(page.locator('#emocao')).toHaveText('feliz');
  await expect(page.locator('#frase')).toHaveText('Oi! Eu sou o BMO.');
  await expect(page.locator('#estado')).toHaveText('pronto');
});

test('erro do servidor aparece e libera a tela', async ({ page }) => {
  await page.evaluate(() => window.__bmoTest.send('erro'));

  await expect(page.locator('#erro')).toContainText('teste de erro');
  await expect(page.locator('#estado')).toHaveText('pronto');
});

test('resposta longa não deixa a tela presa', async ({ page }) => {
  // Cada frase nova substitui a anterior no mesmo #frase (igual ao pipeline
  // real). Guardar o histórico para não depender de um texto que fica na
  // tela só por instantes.
  await page.evaluate(() => {
    window.__frases = [];
    const el = document.getElementById('frase');
    new MutationObserver(() => {
      const texto = el.textContent;
      if (texto && window.__frases[window.__frases.length - 1] !== texto) {
        window.__frases.push(texto);
      }
    }).observe(el, { childList: true, characterData: true, subtree: true });
  });

  await page.evaluate(() => window.__bmoTest.send('longo'));

  await expect.poll(() => page.evaluate(() => window.__frases.join(' | ')))
    .toContain('robô pequeno');
  await expect(page.locator('#frase')).toHaveText('E os dois viraram amigos para sempre.');
  await expect(page.locator('#estado')).toHaveText('pronto', { timeout: 15_000 });
});

test('botão com microfone falso envia áudio e recebe resposta', async ({ page }) => {
  const btn = page.locator('#btn');
  await btn.dispatchEvent('pointerdown', { pointerId: 1, pointerType: 'mouse' });
  await expect(btn).toHaveClass(/recording/);
  // O MediaRecorder só existe depois que o getUserMedia resolve: soltar o
  // botão antes disso não manda áudio nenhum e a resposta não chega.
  await page.waitForFunction(() => window.__bmoTest?.audio?.recorder != null);
  await page.waitForTimeout(800);
  await btn.dispatchEvent('pointerup', { pointerId: 1, pointerType: 'mouse' });

  await expect(page.locator('#transcricao')).toContainText('ouvi: oi bmo', { timeout: 10_000 });
});

test('reconecta sozinho depois de fechar o socket', async ({ page }) => {
  await page.evaluate(() => window.__bmoTest.closeSocket());

  await expect(page.locator('#estado')).toHaveText('desconectado');
  await expect(page.locator('#estado')).toContainText('pronto', { timeout: 5_000 });
});

test('microfone negado mostra mensagem e não fica gravando', async ({ page }) => {
  await page.addInitScript(() => {
    navigator.mediaDevices.getUserMedia = () => Promise.reject(
      Object.assign(new Error('denied'), { name: 'NotAllowedError' }),
    );
  });
  await page.goto('/?e2e=1');

  await page.locator('#btn').dispatchEvent('pointerdown', { pointerId: 1, pointerType: 'mouse' });

  await expect(page.locator('#erro')).toContainText('Microfone bloqueado');
  await expect(page.locator('#btn')).not.toHaveClass(/recording/);
});

test('pointerdown durante a fala para áudio e animação na hora', async ({ page }) => {
  await page.evaluate(() => {
    window.__bmoTest.bmo.playAnimation('dancar', 10);
    window.__bmoTest.audio.playChunk(new Int16Array(24000).buffer);
  });

  await page.locator('#btn').dispatchEvent('pointerdown', { pointerId: 1, pointerType: 'mouse' });

  const depois = await page.evaluate(() => ({
    fontes: window.__bmoTest.audio._sources.length,
    animacao: window.__bmoTest.bmo._animation,
  }));
  expect(depois.fontes).toBe(0);
  expect(depois.animacao).toBeNull();

  // O servidor confirma o corte com "parar"...
  await expect.poll(() => page.evaluate(() => window.__bmoTest.lastJson?.type)).toBe('parar');

  // ... e o "parar" não pode tirar o botão do estado "gravando": senão o
  // pointerup não solta a gravação e o microfone fica aberto.
  await expect(page.locator('#btn')).toHaveText('Ouvindo…');

  await page.locator('#btn').dispatchEvent('pointerup', { pointerId: 1, pointerType: 'mouse' });
});
