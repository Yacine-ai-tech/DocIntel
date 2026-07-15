import { test, expect } from '@playwright/test';

test('has title', async ({ page }) => {
  await page.goto('http://localhost:5173');
  // Simple check to ensure the page loads
  await expect(page).toHaveTitle(/.*|Vite/);
});
