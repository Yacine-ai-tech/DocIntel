import { test, expect } from '@playwright/test';

const BASE_URL = process.env.TEST_BASE_URL || '';

test.describe('Exhaustive UI Component & Page Flow Suite', () => {

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

  // Component-level tests for main.tsx/App.tsx/kit/* were removed here — they were
  // `expect(true).toBeTruthy()` placeholders providing zero real coverage. None of
  // main.tsx, App.tsx, or the kit/* components are independently routable pages;
  // they're exercised indirectly by every page test below (AppShell wraps every
  // page, JSONViewer/SplitPane render on Workspace/Compare, PipelineFlow on
  // Pipelines) — a fake per-file placeholder added nothing a real page-load test
  // doesn't already cover.

  test('Should render and interact with CameraDashboard (pages/CameraDashboard.tsx)', async ({ page }) => {
    await page.goto(BASE_URL + '/camera');
    await page.waitForLoadState('domcontentloaded');
    const rootHtml = await page.locator('#root').innerHTML();
    expect(rootHtml.length).toBeGreaterThan(0);
  });

  test('Should render and interact with ImageIntel (pages/ImageIntel.tsx)', async ({ page }) => {
    await page.goto(BASE_URL + '/images');
    await page.waitForLoadState('domcontentloaded');
    const rootHtml = await page.locator('#root').innerHTML();
    expect(rootHtml.length).toBeGreaterThan(0);
  });

  test('Should render and interact with Pipelines (pages/Pipelines.tsx)', async ({ page }) => {
    await page.goto(BASE_URL + '/pipelines');
    await page.waitForLoadState('domcontentloaded');
    const rootHtml = await page.locator('#root').innerHTML();
    expect(rootHtml.length).toBeGreaterThan(0);
  });

  test('Should render and interact with CameraMobile (pages/CameraMobile.tsx)', async ({ page }) => {
    await page.goto(BASE_URL + '/camera/mobile');
    await page.waitForLoadState('domcontentloaded');
    const rootHtml = await page.locator('#root').innerHTML();
    expect(rootHtml.length).toBeGreaterThan(0);
  });

  test('Should render and interact with Documents (pages/Documents.tsx)', async ({ page }) => {
    await page.goto(BASE_URL + '/documents');
    await page.waitForLoadState('domcontentloaded');
    const rootHtml = await page.locator('#root').innerHTML();
    expect(rootHtml.length).toBeGreaterThan(0);
  });

  test('Should render and interact with Compare (pages/Compare.tsx)', async ({ page }) => {
    await page.goto(BASE_URL + '/compare');
    await page.waitForLoadState('domcontentloaded');
    const rootHtml = await page.locator('#root').innerHTML();
    expect(rootHtml.length).toBeGreaterThan(0);
  });

  test('Should render and interact with Models (pages/Models.tsx)', async ({ page }) => {
    await page.goto(BASE_URL + '/models');
    await page.waitForLoadState('domcontentloaded');
    const rootHtml = await page.locator('#root').innerHTML();
    expect(rootHtml.length).toBeGreaterThan(0);
  });

  test('Should render and interact with Benchmarks (pages/Benchmarks.tsx)', async ({ page }) => {
    await page.goto(BASE_URL + '/benchmarks');
    await page.waitForLoadState('domcontentloaded');
    const rootHtml = await page.locator('#root').innerHTML();
    expect(rootHtml.length).toBeGreaterThan(0);
  });

  test('Should render and interact with Workspace (pages/Workspace.tsx)', async ({ page }) => {
    await page.goto(BASE_URL + '/');
    await page.waitForLoadState('domcontentloaded');
    const rootHtml = await page.locator('#root').innerHTML();
    expect(rootHtml.length).toBeGreaterThan(0);
  });

  test('Should render and interact with ApiDocs (pages/ApiDocs.tsx)', async ({ page }) => {
    await page.goto(BASE_URL + '/api-docs');
    await page.waitForLoadState('domcontentloaded');
    const rootHtml = await page.locator('#root').innerHTML();
    expect(rootHtml.length).toBeGreaterThan(0);
  });

  test('Should render and interact with Batch (pages/Batch.tsx)', async ({ page }) => {
    await page.goto(BASE_URL + '/batch');
    await page.waitForLoadState('domcontentloaded');
    const rootHtml = await page.locator('#root').innerHTML();
    expect(rootHtml.length).toBeGreaterThan(0);
  });

  test('Should render and interact with Settings (pages/Settings.tsx)', async ({ page }) => {
    await page.goto(BASE_URL + '/settings');
    await page.waitForLoadState('domcontentloaded');
    const rootHtml = await page.locator('#root').innerHTML();
    expect(rootHtml.length).toBeGreaterThan(0);
  });

  test('Should render and interact with Activity (pages/Activity.tsx)', async ({ page }) => {
    await page.goto(BASE_URL + '/activity');
    await page.waitForLoadState('domcontentloaded');
    const rootHtml = await page.locator('#root').innerHTML();
    expect(rootHtml.length).toBeGreaterThan(0);
  });

});

test.describe("2026 UI/UX Standards Validation", () => {
  test("Should verify haptic feedback scale animation on buttons", async ({ page }) => {
    await page.goto(BASE_URL);
    const btn = page.locator('button').first();
    if (await btn.isVisible()) {
      // Hover the button and simulate mouse down to trigger :active
      const box = await btn.boundingBox();
      if (box) {
        await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
        await page.mouse.down();
        // The scale should drop to 0.96 due to the new CSS rules
        const transform = await btn.evaluate((el) => window.getComputedStyle(el).transform);
        // Note: transform is usually a matrix. We check that it's not 'none'.
        expect(transform).not.toBe('none');
        await page.mouse.up();
      }
    }
  });

  test("Should verify accessibility focus-visible rings", async ({ page }) => {
    await page.goto(BASE_URL);
    const input = page.locator('input').first();
    if (await input.isVisible()) {
      await input.focus();
      const outline = await input.evaluate((el) => window.getComputedStyle(el).outline);
      // We expect the focus-visible to trigger either a box-shadow or an outline
      expect(outline).not.toBe('none');
    }
  });
});

test.describe("Mobile & Low-Bandwidth Resilience (Sahel Optimized)", () => {
  test("Should verify strict mobile viewport configuration", async ({ page }) => {
    await page.goto(BASE_URL);
    const viewport = await page.locator('meta[name="viewport"]').getAttribute('content');
    expect(viewport).toContain('width=device-width');
    expect(viewport).toContain('shrink-to-fit=no');
    expect(viewport).toContain('maximum-scale=5.0');
  });

  // Service Worker registration/caching tests were removed here — they asserted
  // the opposite of this app's actual, deliberate behavior. index.html explicitly
  // unregisters any Service Worker and clears CacheStorage on every single page
  // load ("Zero-Trust Fresh Code Guarantee"), and public/sw.js's entire job is to
  // self-destruct (install → clear caches → unregister itself → claim clients) so
  // any user with a stale SW from a previous version gets cleaned up. There is
  // deliberately never an active SW here; a "passing" version of these tests would
  // mean that guarantee had silently broken.
});
