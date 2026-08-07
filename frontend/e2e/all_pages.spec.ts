import { test, expect } from '@playwright/test';

const BASE_URL = process.env.TEST_BASE_URL || BASE_URL + '';

const ROUTES = ['/', '/documents', '/images', '/camera', '/pipelines', '/compare', '/batch', '/benchmarks', '/models', '/activity', '/settings'];

test.describe('DocIntel All Pages E2E Suite', () => {

  test.beforeEach(async ({ page }) => {
    await page.route('**/*', async route => {
      const req = route.request();
      const url = req.url();
      if ((req.resourceType() === 'fetch' || req.resourceType() === 'xhr') && url.includes('vercel.app')) {
        let backendUrl = process.env.STAGING_INTELAI_URL ;
        if (url.includes('docintel-ui')) backendUrl = process.env.STAGING_DOCINTEL_URL ;
        else if (url.includes('agentkit-ui')) backendUrl = process.env.STAGING_AGENTKIT_URL ;
        else if (url.includes('rageval-ui')) backendUrl = process.env.STAGING_RAGEVAL_URL ;
        else if (url.includes('voiceflow-ui')) backendUrl = process.env.STAGING_VOICEFLOW_URL ;
        else if (url.includes('streampulse-ui')) backendUrl = process.env.STAGING_STREAMPULSE_URL ;
        
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
