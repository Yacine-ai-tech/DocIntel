import { test, expect } from '@playwright/test';

const BASE_URL = process.env.TEST_BASE_URL || BASE_URL + '';

const ROUTES = ['/', '/documents', '/images', '/camera', '/pipelines', '/compare', '/batch', '/benchmarks', '/models', '/activity', '/settings'];

test.describe('DocIntel All Pages E2E Suite', () => {
  for (const route of ROUTES) {
    test(`Should successfully load ${route} page without crashing`, async ({ page }) => {
      await page.goto(route);
      // Wait for DOM to load
      await page.waitForLoadState('domcontentloaded');

      // Ensure the blank screen of death did not occur
      const rootHtml = await page.locator('#root').innerHTML();
      expect(rootHtml.length).toBeGreaterThan(0);

      // Ensure no generic "An unexpected error occurred" overlay
      const errorOverlay = page.locator('text=unexpected error');
      await expect(errorOverlay).not.toBeVisible();
    });
  }
});
