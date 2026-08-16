import { test, expect } from '@playwright/test';

const BASE_URL = process.env.TEST_BASE_URL || '';

const ROUTES = ['/', '/documents', '/images', '/camera', '/pipelines', '/compare', '/batch', '/benchmarks', '/models', '/activity', '/settings'];

test.describe('DocIntel All Pages E2E Suite', () => {

  test.beforeEach(async ({ page }) => {
    // When run against a Vercel-hosted preview of this frontend, rewrite its API
    // calls to the deployed backend under test instead of Vercel's own origin.
    await page.route('**/*', async route => {
      const req = route.request();
      const url = req.url();
      if ((req.resourceType() === 'fetch' || req.resourceType() === 'xhr') &&
          url.includes('vercel.app') && url.includes('docintel-ui')) {
        const backendUrl = process.env.STAGING_DOCINTEL_URL || 'https://docintel-mm79.onrender.com';
        const pathPart = new URL(url).pathname;
        const newUrl = backendUrl.replace(/\/$/, '') + pathPart;
        await route.continue({ url: newUrl });
      } else {
        await route.continue();
      }
    });
  });

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
