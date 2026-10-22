import { expect, test } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.goto('/?e2e=1');
  await expect(page.locator('#estado')).toContainText('pronto');
});

test('executa as cinco ações e mantém a fala', async ({ page }) => {
  await page.evaluate(() => window.__bmoTest.send('acoes'));

  await expect(page.locator('#frase')).toHaveText('Olha eu pulando!');
  await expect(page.locator('#emocao')).toHaveText('feliz');

  // A frase aparece já na quarta ação (a de texto), então a quinta (o som)
  // pode ainda não ter chegado: espera as cinco antes de olhar a lista.
  await expect
    .poll(() => page.evaluate(() => window.__bmoTest.actions.length))
    .toBe(5);

  const estado = await page.evaluate(() => ({
    led: window.__bmoTest.bmo.ledColor,
    animation: window.__bmoTest.bmo._animation?.nome ?? null,
    acoes: window.__bmoTest.actions.map((a) => a.nome),
  }));

  expect(estado.led).toBe('#ff0000');
  expect(estado.animation).toBe('pular');
  expect(estado.acoes).toEqual(['expressao', 'animacao', 'texto', 'led', 'som']);
});

test('ação desconhecida não quebra a resposta', async ({ page }) => {
  await page.evaluate(() => window.__bmoTest.send('acao_invalida'));

  await expect(page.locator('#frase')).toHaveText('Continuo aqui!');
  await expect(page.locator('#erro')).toHaveText('');
  const animation = await page.evaluate(() => window.__bmoTest.bmo._animation);
  expect(animation).toBeNull();
});

test('bravo não deixa o corpo deslocado depois de voltar ao neutro', async ({ page }) => {
  await page.evaluate(() => window.__bmoTest.bmo.setEmotion('bravo'));
  await page.waitForTimeout(300);
  await page.evaluate(() => window.__bmoTest.bmo.setEmotion('neutro'));
  await page.waitForTimeout(200);

  const x = await page.evaluate(() => window.__bmoTest.bmo.group.position.x);
  expect(Math.abs(x)).toBeLessThan(0.001);
});

test('animação termina e limpa o estado', async ({ page }) => {
  await page.evaluate(() => window.__bmoTest.bmo.playAnimation('pular', 1.0));
  await page.waitForTimeout(150);
  const y = await page.evaluate(() => window.__bmoTest.bmo.group.position.y);
  expect(y).toBeGreaterThan(0.05);

  await page.waitForTimeout(1100);
  const animation = await page.evaluate(() => window.__bmoTest.bmo._animation);
  expect(animation).toBeNull();
});

// O maior deslocamento lateral do corpo ao longo de vários quadros. A pose
// do "bravo" oscila (position.x = sin(t*24)*0.02), então um único quadro
// pode pegar o instante em que ela passa pelo zero: só o maior valor ao
// longo de vários quadros diz se o deslocamento aconteceu.
async function maxDeslocamentoX(page, quadros = 12) {
  return page.evaluate(async (n) => {
    const bmo = window.__bmoTest.bmo;
    let max = 0;
    for (let i = 0; i < n; i += 1) {
      await new Promise((resolve) => requestAnimationFrame(resolve));
      max = Math.max(max, Math.abs(bmo.group.position.x));
    }
    return max;
  }, quadros);
}

test('pensando tem prioridade sobre a pose da expressão', async ({ page }) => {
  await page.evaluate(() => {
    const bmo = window.__bmoTest.bmo;
    bmo.setEmotion('bravo');
    bmo.setState('pensando');
  });

  // Enquanto o BMO pensa, ele balança no lugar: o deslocamento lateral do
  // "bravo" não aparece.
  expect(await maxDeslocamentoX(page)).toBeLessThan(0.001);

  // A expressão continua guardada...
  expect(await page.evaluate(() => window.__bmoTest.bmo.emotion)).toBe('bravo');

  // ... e volta sozinha quando o estado deixa de ser "pensando".
  await page.evaluate(() => window.__bmoTest.bmo.setState('pronto'));
  expect(await maxDeslocamentoX(page)).toBeGreaterThan(0.001);
});

test('setLed guarda a cor mesmo sem nenhuma malha de LED', async ({ page }) => {
  const resultado = await page.evaluate(() => {
    const bmo = window.__bmoTest.bmo;
    bmo.leds = []; // sem malha de LED: o modelo ainda não carregou
    let erro = null;
    try {
      bmo.setLed('#ff0000');
    } catch (e) {
      erro = String(e);
    }
    return { erro, cor: bmo.ledColor };
  });

  expect(resultado.erro).toBeNull();
  expect(resultado.cor).toBe('#ff0000');
});
