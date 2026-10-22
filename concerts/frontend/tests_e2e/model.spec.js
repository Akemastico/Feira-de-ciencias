import { expect, test } from '@playwright/test';

test('o modelo real carrega e o procedural fica escondido', async ({ page }) => {
  const status = [];
  page.on('response', (r) => {
    if (r.url().includes('/assets/bmo.glb')) status.push(r.status());
  });

  await page.goto('/?e2e=1');
  await expect(page.locator('#estado')).toContainText('pronto');
  await page.waitForFunction(() => window.__bmoTest?.bmo?.model !== null, null, { timeout: 10_000 });

  const estado = await page.evaluate(() => ({
    temModel: window.__bmoTest.bmo.model !== null,
    proceduralVisivel: window.__bmoTest.bmo._procedural.visible,
    leds: window.__bmoTest.bmo.leds.length,
    rig: Object.keys(window.__bmoTest.bmo.rig),
  }));

  expect(status).toContain(200);
  expect(estado.temModel).toBe(true);
  expect(estado.proceduralVisivel).toBe(false);
  expect(estado.leds).toBeGreaterThan(0);
  expect(estado.rig).toContain('rosto');
});

test('trocar a expressão troca a textura do rosto', async ({ page }) => {
  await page.goto('/?e2e=1');
  await page.waitForFunction(() => window.__bmoTest?.bmo?.model !== null, null, { timeout: 10_000 });

  await page.evaluate(() => window.__bmoTest.bmo.setEmotion('bravo'));

  // A textura entra por rede: espera a URL aparecer em vez de dormir um tempo fixo.
  await expect
    .poll(async () => page.evaluate(() => {
      const rosto = window.__bmoTest.bmo.rig.rosto;
      const mat = Array.isArray(rosto.material) ? rosto.material[0] : rosto.material;
      return mat?.map?.image?.src ?? null;
    }))
    .toContain('rostos/7.png');
});

test('os braços ficam para baixo, longe da pose em T', async ({ page }) => {
  await page.goto('/?e2e=1');
  await page.waitForFunction(() => window.__bmoTest?.bmo?.model !== null, null, { timeout: 10_000 });

  const posicoes = await page.evaluate(() => {
    const b = window.__bmoTest.bmo;
    const mundo = (obj) => {
      obj.updateWorldMatrix(true, false);
      return obj.getWorldPosition(new obj.position.constructor());
    };
    const maoL = mundo(b.rig.handL);
    const maoR = mundo(b.rig.handR);
    const ombroL = mundo(b.rig.shoulderL);
    const ombroR = mundo(b.rig.shoulderR);
    return {
      maoL: [maoL.x, maoL.y, maoL.z],
      maoR: [maoR.x, maoR.y, maoR.z],
      ombroL: [ombroL.x, ombroL.y, ombroL.z],
      ombroR: [ombroR.x, ombroR.y, ombroR.z],
    };
  });

  // Mão bem abaixo do ombro (braço descendo, não esticado para o lado).
  expect(posicoes.maoL[1]).toBeLessThan(posicoes.ombroL[1] - 0.3);
  expect(posicoes.maoR[1]).toBeLessThan(posicoes.ombroR[1] - 0.3);
  // E visível: fora do corpo (o corpo tem ~1.5 de largura, ou seja |x| < 0.75).
  expect(Math.abs(posicoes.maoL[0])).toBeGreaterThan(0.75);
  expect(Math.abs(posicoes.maoR[0])).toBeGreaterThan(0.75);
});

test('sem o arquivo do modelo o BMO procedural continua aparecendo', async ({ page }) => {
  await page.route('**/assets/bmo.glb', (route) => route.fulfill({ status: 404, body: '' }));

  await page.goto('/?e2e=1');
  await expect(page.locator('#estado')).toContainText('pronto');
  await page.waitForTimeout(800);

  const estado = await page.evaluate(() => ({
    model: window.__bmoTest.bmo.model,
    proceduralVisivel: window.__bmoTest.bmo._procedural.visible,
  }));

  expect(estado.model).toBeNull();
  expect(estado.proceduralVisivel).toBe(true);
});
