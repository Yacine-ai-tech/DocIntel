# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: docintel_specialized.spec.ts >> Phase 4.1 — DocIntel UI Workflows >> All main navigation pages render without crash
- Location: e2e/docintel_specialized.spec.ts:42:3

# Error details

```
Error: page.goto: net::ERR_NAME_NOT_RESOLVED at https://activity/
Call log:
  - navigating to "https://activity/", waiting until "load"

```

# Test source

```ts
  1   | import { test, expect, Page } from '@playwright/test';
  2   | import * as path from 'path';
  3   | import * as fs from 'fs';
  4   | 
  5   | /**
  6   |  * DocIntel — Comprehensive E2E Suite
  7   |  * Phase 4: Specialized Intelligence (DocIntel)
  8   |  * Phase 6: Extended UI/UX Validation
  9   |  * Phase 8: Deep Component Integration (Vector DB + RAG Pipeline)
  10  |  */
  11  | 
  12  | const BASE_URL = process.env.DOCINTEL_URL     || process.env.TEST_BASE_URL || '/';
  13  | const API_URL  = process.env.DOCINTEL_API_URL  || '/';
  14  | const AUTH_URL = process.env.INTELAI_API_URL   || '/';
  15  | 
  16  | async function getAuthToken(request: any): Promise<string> {
  17  |   const resp = await request.post(`${AUTH_URL}/api/login`, {
  18  |     data: { username: 'admin', password: 'fLNtwDH2VaQLbO' }
  19  |   }).catch(() => null);
  20  |   if (resp && resp.ok()) {
  21  |     const body = await resp.json();
  22  |     return body.access_token || body.token || '';
  23  |   }
  24  |   return '';
  25  | }
  26  | 
  27  | async function loginUI(page: Page) {
  28  |   await page.goto(`${BASE_URL}/`);
  29  |   await page.waitForLoadState('domcontentloaded');
  30  | }
  31  | 
  32  | async function assertNoReactCrash(page: Page) {
  33  |   const crash = page.locator('text=/An unexpected error occurred|Something went wrong|ChunkLoadError/i');
  34  |   await expect(crash).toHaveCount(0);
  35  | }
  36  | 
  37  | // ─────────────────────────────────────────────────────────────────────────────
  38  | // Phase 4.1 — DocIntel UI Workflows
  39  | // ─────────────────────────────────────────────────────────────────────────────
  40  | test.describe('Phase 4.1 — DocIntel UI Workflows', () => {
  41  | 
  42  |   test('All main navigation pages render without crash', async ({ page }) => {
  43  |     await loginUI(page);
  44  |     const routes = [
  45  |       '/activity', '/batch', '/benchmarks', '/compare',
  46  |       '/documents', '/imageintel', '/models', '/pipelines'
  47  |     ];
  48  |     for (const route of routes) {
> 49  |       await page.goto(`${'/'}${route}`);
      |                  ^ Error: page.goto: net::ERR_NAME_NOT_RESOLVED at https://activity/
  50  |       await page.waitForLoadState('domcontentloaded');
  51  |       await assertNoReactCrash(page);
  52  |       await expect(page.locator('body')).toBeVisible();
  53  |       console.log(`✅ ${route} — OK`);
  54  |     }
  55  |   });
  56  | 
  57  |   test('Documents page: file upload via input', async ({ page }) => {
  58  |     await loginUI(page);
  59  |     await page.goto(`${BASE_URL}/documents`);
  60  |     await page.waitForLoadState('domcontentloaded', { timeout: 15000 }).catch(() => {});
  61  |     await assertNoReactCrash(page);
  62  | 
  63  |     // Check if file upload input exists
  64  |     const fileInput = page.locator('input[type="file"]').first();
  65  |     if (await fileInput.isVisible({ timeout: 5000 }).catch(() => false)) {
  66  |       // Create a temp PDF for upload
  67  |       const tmpPdf = path.join('/tmp', 'test_upload.pdf');
  68  |       fs.writeFileSync(tmpPdf, Buffer.from('%PDF-1.4\n1 0 obj\n<</Type /Catalog>>\nendobj\n', 'utf-8'));
  69  |       await fileInput.setInputFiles(tmpPdf);
  70  |       await page.waitForTimeout(2000);
  71  |       // Should not crash; may show progress or success
  72  |       await assertNoReactCrash(page);
  73  |       fs.unlinkSync(tmpPdf);
  74  |     }
  75  |   });
  76  | 
  77  |   test('Documents page: uploading corrupted file shows error — not crash', async ({ page }) => {
  78  |     await loginUI(page);
  79  |     await page.goto(`${BASE_URL}/documents`);
  80  |     await page.waitForLoadState('domcontentloaded');
  81  |     await assertNoReactCrash(page);
  82  | 
  83  |     const fileInput = page.locator('input[type="file"]').first();
  84  |     if (await fileInput.isVisible({ timeout: 5000 }).catch(() => false)) {
  85  |       const tmpCorrupt = path.join('/tmp', 'corrupt.pdf');
  86  |       fs.writeFileSync(tmpCorrupt, Buffer.from('this is not a pdf', 'utf-8'));
  87  |       await fileInput.setInputFiles(tmpCorrupt);
  88  |       await page.waitForTimeout(2000);
  89  |       await assertNoReactCrash(page);
  90  |       // Should show an error/warning
  91  |       const errorEl = page.locator('text=/error|invalid|failed|unsupported/i').first();
  92  |       // Even if no explicit error shown, the app must not crash
  93  |       fs.unlinkSync(tmpCorrupt);
  94  |     }
  95  |   });
  96  | 
  97  |   test('Batch page: job status polling elements visible', async ({ page }) => {
  98  |     await loginUI(page);
  99  |     await page.goto(`${BASE_URL}/batch`);
  100 |     await page.waitForLoadState('domcontentloaded', { timeout: 15000 }).catch(() => {});
  101 |     await assertNoReactCrash(page);
  102 |     // Look for job/status table or list
  103 |     const statusEl = page.locator('table, .job-list, [data-testid="batch"], text=/batch|job|queue/i').first();
  104 |     if (await statusEl.isVisible({ timeout: 5000 }).catch(() => false)) {
  105 |       await expect(statusEl).toBeVisible();
  106 |     }
  107 |   });
  108 | });
  109 | 
  110 | // ─────────────────────────────────────────────────────────────────────────────
  111 | // Phase 4.1 — DocIntel API Tests
  112 | // ─────────────────────────────────────────────────────────────────────────────
  113 | test.describe('Phase 4.1 — DocIntel API Validation', () => {
  114 | 
  115 |   test('GET /health returns 200', async ({ request }) => {
  116 |     const resp = await request.get(`${API_URL}/health`).catch(() => null);
  117 |     if (resp) expect(resp.status()).toBeLessThan(500);
  118 |   });
  119 | 
  120 |   test('GET /api/documents requires authentication', async ({ request }) => {
  121 |     const resp = await request.get(`${API_URL}/api/documents`).catch(() => null);
  122 |     if (resp) expect([200, 401, 403]).toContain(resp.status());
  123 |   });
  124 | 
  125 |   test('POST /api/documents/upload with valid PDF succeeds', async ({ request }) => {
  126 |     const token = await getAuthToken(request);
  127 |     if (!token) { test.skip(); return; }
  128 | 
  129 |     // Create a minimal PDF buffer
  130 |     const pdfContent = Buffer.from('%PDF-1.4\n1 0 obj\n<</Type /Catalog>>\nendobj\n', 'utf-8');
  131 |     const resp = await request.post(`${API_URL}/api/documents/upload`, {
  132 |       headers: { Authorization: `Bearer ${token}` },
  133 |       multipart: {
  134 |         file: {
  135 |           name: 'test.pdf',
  136 |           mimeType: 'application/pdf',
  137 |           buffer: pdfContent,
  138 |         }
  139 |       },
  140 |       timeout: 30000,
  141 |     }).catch(() => null);
  142 | 
  143 |     if (resp) {
  144 |       // 200/201 = success, 400 = validation error (file too small/invalid), 422 = schema error
  145 |       // All are acceptable — 500 is NOT
  146 |       expect(resp.status()).not.toBe(500);
  147 |     }
  148 |   });
  149 | 
```