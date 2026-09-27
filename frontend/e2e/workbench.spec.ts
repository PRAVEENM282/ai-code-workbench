import { expect, test } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/health', (route) => route.fulfill({ json: { status: 'ok' } }));
  await page.route('**/api/v1/history*', (route) => route.fulfill({ json: [] }));
});

test('loads Monaco, switches language mode, and opens command palette', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('main', { name: 'Code workbench' })).toBeVisible();
  const language = page.getByLabel('Language');
  await expect(language).toHaveValue('python');
  await language.fill('javascript');
  await expect(language).toHaveValue('javascript');
  await expect(page.locator('.file-tab')).toContainText('main.js');
  await language.fill('madeuplang');
  await expect(language).toHaveValue('madeuplang');
  await expect(page.locator('.file-tab')).toContainText('main.txt');
  await expect(page.locator('.monaco-editor')).toBeVisible();
  await page.getByRole('button', { name: 'Open command palette' }).click();
  await expect(page.getByRole('dialog', { name: 'Command palette' })).toBeVisible();
});

test('shows retryable upstream failure in the result panel', async ({ page }) => {
  await page.route('**/api/v1/generate', (route) => route.fulfill({ status: 502,
    json: { error: { code: 'upstream_provider_failure', message: 'Provider unavailable' } } }));
  await page.goto('/');
  await page.getByLabel('Instruction').fill('Generate a Python function');
  await page.getByRole('button', { name: 'Generate' }).click();
  await expect(page.locator('.request-error')).toContainText('Provider unavailable');
  await expect(page.getByRole('button', { name: 'Retry' })).toBeVisible();
});
