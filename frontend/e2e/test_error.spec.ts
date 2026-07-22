import { test } from '@playwright/test';

const BASE_URL = process.env.TEST_BASE_URL || BASE_URL + '';
test('get error', async ({ page }) => {
  page.on('console', msg => console.log('PAGE LOG:', msg.text()));
  page.on('pageerror', error => console.log('PAGE ERROR:', error.message));
  await page.goto('/', { waitUntil: 'domcontentloaded' });
});
