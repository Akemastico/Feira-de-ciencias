import { expect, test } from '@playwright/test';

// O backend de ensaio responde em poucos milissegundos: o botão passa por
// "Reconhecendo…" e "Pensando…" antes de o navegador conseguir desenhar.
// Por isso o teste guarda o histórico de textos e classes do botão em vez de
// torcer para ver cada estado pintado na tela.
async function vigiarBotao(page) {
  await page.evaluate(() => {
    window.__botao = [];
    const el = document.getElementById('btn');
    const guardar = (txt) => {
      if (!txt) return;
      const ultimo = window.__botao[window.__botao.length - 1];
      if (!ultimo || ultimo.texto !== txt) {
        window.__botao.push({ texto: txt, classe: el.className });
      }
    };
    new MutationObserver((registros) => {
      for (const registro of registros) {
        for (const no of registro.addedNodes) guardar(no.textContent);
      }
    }).observe(el, { childList: true, characterData: true, subtree: true });
    guardar(el.textContent);
  });
}

// Apertar o botão só grava se o MediaRecorder já existir; esperar por ele
// evita soltar antes da hora (aí não há áudio nenhum para enviar).
async function apertar(page) {
  const btn = page.locator('#btn');
  await btn.dispatchEvent('pointerdown', { pointerId: 1, pointerType: 'mouse' });
  await page.waitForFunction(() => window.__bmoTest?.audio?.recorder != null);
  return btn;
}

async function soltar(page) {
  await page.locator('#btn').dispatchEvent('pointerup', { pointerId: 1, pointerType: 'mouse' });
}

test('o botão mostra o ciclo reconhecer → pensar → falar → pronto', async ({ page }) => {
  await page.goto('/?e2e=1');
  await expect(page.locator('#estado')).toContainText('pronto');
  await vigiarBotao(page);

  const btn = await apertar(page);
  await expect(btn).toHaveText('Ouvindo…');
  await soltar(page);

  await expect.poll(() => page.evaluate(() => window.__botao.length)).toBeGreaterThan(2);
  await expect(btn).toHaveText('Segure para falar', { timeout: 20_000 });

  const historico = await page.evaluate(() => window.__botao);
  const textos = historico.map((h) => h.texto);

  // Os estados aparecem nesta ordem.
  const ordem = ['Ouvindo…', 'Reconhecendo…', 'Pensando…', 'Falando…'];
  const posicoes = ordem.map((t) => textos.indexOf(t));
  expect(posicoes.every((p) => p >= 0)).toBe(true);
  expect(posicoes).toEqual([...posicoes].sort((a, b) => a - b));
  expect(textos[textos.length - 1]).toBe('Segure para falar');

  // Enquanto espera, o botão usa a classe que dispara a animação de pulso.
  const esperando = historico.find((h) => h.texto === 'Reconhecendo…' || h.texto === 'Pensando…');
  expect(esperando).toBeTruthy();
  expect(esperando.classe).toContain('esperando');
});

test('sem WebSocket o botão avisa que está sem conexão', async ({ page }) => {
  await page.goto('/?e2e=1');
  await page.evaluate(() => window.__bmoTest.ws.ws.close());

  await apertar(page);
  await soltar(page);

  await expect(page.locator('#btn')).toHaveText('Sem conexão');
  await expect(page.locator('#erro')).toContainText('Sem conexão');

  // Some tempo depois o botão volta ao normal: a tela não fica presa.
  await expect(page.locator('#btn')).toHaveText('Segure para falar', { timeout: 6000 });
  await expect(page.locator('#erro')).toHaveText('');
});

test('sem resposta do backend o botão volta ao normal sozinho', async ({ page }) => {
  await page.goto('/?e2e=1');
  await expect(page.locator('#estado')).toContainText('pronto');
  // O cliente para de olhar as mensagens: para o BMO, não veio resposta.
  await page.evaluate(() => { window.__bmoTest.ws.onJson = () => {}; });

  await apertar(page);
  await soltar(page);

  await expect(page.locator('#btn')).toHaveText('Reconhecendo…');

  // 12 s depois de soltar o botão, a tela não fica congelada esperando.
  await expect(page.locator('#btn')).toHaveText('Segure para falar', { timeout: 20_000 });
  await expect(page.locator('#erro')).toContainText('não respondeu');
});

test('cair a conexão no meio da resposta não deixa o botão preso', async ({ page }) => {
  await page.goto('/?e2e=1');
  await expect(page.locator('#estado')).toContainText('pronto');
  await page.evaluate(() => { window.__bmoTest.ws.onJson = () => {}; });

  await apertar(page);
  await soltar(page);
  await expect(page.locator('#btn')).toHaveText('Reconhecendo…');

  // A conexão cai antes da resposta: sem 'audio_fim' o botão ficaria em
  // "Pensando…" para sempre.
  await page.evaluate(() => window.__bmoTest.ws.ws.close());

  await expect(page.locator('#btn')).toHaveText('Sem conexão');
  await expect(page.locator('#erro')).toContainText('Sem conexão');
});
