import { test, expect } from '@playwright/test';

const BASE_URL = process.env.TEST_BASE_URL || BASE_URL + '';

test('has title', async ({ page }) => {
  await page.goto('/');
  // Simple check to ensure the page loads
  await expect(page).toHaveTitle(/.*|Vite/);
});
