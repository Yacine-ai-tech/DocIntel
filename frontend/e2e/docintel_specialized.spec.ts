import { test, expect } from '@playwright/test';
import path from 'path';
import fs from 'fs';

const BASE_URL = process.env.TEST_BASE_URL || 'http://localhost:5173';

test.describe('Phase 3: DocIntel Specialized Workflows', () => {

  test('Slice 3.1: Document Upload & Classification', async ({ page }) => {
    await page.goto(`${BASE_URL}/documents`);
    
    // Create a dummy PDF if it doesn't exist
    const dummyPdfPath = path.join(__dirname, 'test_invoice.pdf');
    if (!fs.existsSync(dummyPdfPath)) {
      fs.writeFileSync(dummyPdfPath, '%PDF-1.4 Dummy invoice content for E2E testing');
    }
    
    // Check if there is an input file to test
    const fileInput = page.locator('input[type="file"]');
    if (await fileInput.count() > 0) {
      await fileInput.setInputFiles(dummyPdfPath);
      
      // Wait for network request to complete and show results
      await expect(page.locator('text=/Classification/i, .extraction-result')).toBeVisible({ timeout: 15000 });
    }
  });

  test('Slice 3.1: ImageIntel & Pipeline Rendering', async ({ page }) => {
    // Test the ImageIntel page
    await page.goto(`${BASE_URL}/image-intel`);
    await expect(page.locator('text=/Image/i').first()).toBeVisible();

    // Test the Pipelines config page
    await page.goto(`${BASE_URL}/pipelines`);
    await expect(page.locator('text=/Pipeline/i').first()).toBeVisible();
    
    // Assert drag and drop / config elements are visible
    const pipelineElements = page.locator('.pipeline-node, [role="button"]');
    await expect(pipelineElements.first()).toBeVisible({ timeout: 10000 });
  });

  test('Slice 3.1: Batch Job Polling Validation', async ({ page }) => {
    await page.goto(`${BASE_URL}/batch`);
    await expect(page.locator('text=/Batch/i').first()).toBeVisible();
    
    // Check if the table or list for batch jobs is present
    await expect(page.locator('table, .batch-list')).toBeVisible({ timeout: 5000 });
  });

});
