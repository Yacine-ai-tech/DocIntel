import { test } from '@playwright/test';
test('get error', async ({ page }) => {
  page.on('console', msg => console.log('PAGE LOG:', msg.text()));
  page.on('pageerror', error => console.log('PAGE ERROR:', error.message));
  await page.goto('http://localhost:5174', { waitUntil: 'networkidle' });
});
