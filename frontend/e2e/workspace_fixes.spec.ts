import { test, expect } from '@playwright/test';
import path from 'path';
import fs from 'fs';

// Regression tests for two Workspace.tsx findings fixed this session:
//   - the primary upload dropzone was not keyboard-accessible at all
//   - dropping a new file mid-extraction could race the in-flight request and
//     silently attribute a stale result to the wrong file

const TEST_PDF = path.join('/tmp', 'workspace_fixes_test.pdf');
const TEST_PNG = path.join('/tmp', 'workspace_fixes_test2.png');

test.beforeAll(() => {
  // Minimal valid single-page PDF — enough to pass a file-type check without
  // needing a real document.
  fs.writeFileSync(
    TEST_PDF,
    '%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n' +
      '3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF',
  );
  // 1x1 PNG
  fs.writeFileSync(
    TEST_PNG,
    Buffer.from(
      '89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de' +
        '0000000c49444154789c63f8cfc0000003010100c9fe92ef0000000049454e44ae426082',
      'hex',
    ),
  );
});

// App.tsx gates the whole route tree behind a real /health check on mount
// (shows a "waking up the backend" screen while health is "checking"/"down") —
// with no backend running against this dev server, that call would otherwise
// hang the app on that screen forever and never render Workspace at all.
async function mockHealthy(page: import('@playwright/test').Page) {
  await page.route('**/health', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'ok', service: 'docintel', version: 'test' }),
    }),
  );
}

test.describe('Workspace upload zone — keyboard accessibility', () => {
  test('dropzone is reachable and operable via keyboard alone', async ({ page }) => {
    await mockHealthy(page);
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    const dropzone = page.getByRole('button', { name: /upload a document/i });
    await expect(dropzone).toBeVisible();

    // Must be reachable by Tab (not skipped, unlike before this fix — the div
    // had no tabIndex and its actual <input type="file"> was display:none'd
    // out of the tab order entirely).
    await dropzone.focus();
    await expect(dropzone).toBeFocused();

    // Pressing Enter must open the native file picker — verified via the
    // filechooser event Playwright exposes, which only fires on a real
    // click()-equivalent activation of the file input.
    const chooserPromise = page.waitForEvent('filechooser');
    await page.keyboard.press('Enter');
    const chooser = await chooserPromise;
    expect(chooser).toBeTruthy();
    await chooser.setFiles(TEST_PNG);
  });
});

test.describe('Workspace upload zone — mid-extraction file-swap guard', () => {
  test('dropping a new file while a request is in flight does not change the active document', async ({ page }) => {
    // Delay /process's response so there's a real, controllable window to
    // attempt dropping a second file while the first is still "working" —
    // an uncontrolled live backend call can't be timed deterministically.
    await page.route('**/process', async (route) => {
      await new Promise((r) => setTimeout(r, 3000));
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          route: 'ocr_fallback', doc_type: 'invoice', confidence: 0.9,
          page_count: 1, processing_time_ms: 3000, fields: { vendor: 'FIRST_FILE_VENDOR' },
        }),
      });
    });
    await mockHealthy(page);

    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    const fileInput = page.locator('input[type="file"]').first();
    await fileInput.setInputFiles(TEST_PDF);
    await expect(page.getByText('workspace_fixes_test.pdf')).toBeVisible();

    const analyzeButton = page.getByRole('button', { name: /analyze/i });
    await analyzeButton.click();
    await expect(page.getByRole('button', { name: /processing/i })).toBeVisible();

    // Attempt to drop a second file while the first request is still in flight —
    // previously this reset the UI to look idle/ready for the new file while the
    // first request's result would still land and silently overwrite it. With the
    // fix, pickFile() no-ops entirely while phase === "working".
    const dt = await page.evaluateHandle(() => new DataTransfer());
    await fileInput.setInputFiles(TEST_PNG);

    // The originally-selected file must still be the one shown — the second
    // selection while busy must not have been accepted.
    await expect(page.getByText('workspace_fixes_test.pdf')).toBeVisible();
    await expect(page.getByText('workspace_fixes_test2.png')).not.toBeVisible();

    // Let the first request resolve, and confirm ITS result is what's shown —
    // not silently discarded, not attributed to a different file. Extracted
    // fields render as editable textbox values, not plain text nodes, so
    // assert on value rather than getByText.
    await expect(page.getByRole('textbox').first()).toHaveValue(/FIRST_FILE_VENDOR/i, { timeout: 10000 });
    await dt.dispose();
  });
});
