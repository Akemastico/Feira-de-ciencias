import { expect, test } from '@playwright/test';

test('carrega o BMO, cria o canvas e conecta no WebSocket', async ({ page }) => {
  await page.goto('/');

  await expect(page).toHaveTitle('BMO-LLM');
  await expect(page.locator('#scene canvas')).toBeVisible();
  await expect(page.locator('#estado')).toContainText('pronto', { timeout: 10_000 });
});
