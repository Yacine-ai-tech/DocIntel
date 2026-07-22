# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: exhaustive_ui.spec.ts >> Mobile & Low-Bandwidth Resilience (Sahel Optimized) >> Should verify Service Worker uses Network-First strategy for documents to prevent stale cache
- Location: e2e/exhaustive_ui.spec.ts:236:3

# Error details

```
Test timeout of 45000ms exceeded.
```

```
Error: page.evaluate: Test timeout of 45000ms exceeded.
```

# Page snapshot

```yaml
- generic [ref=e3]:
  - generic [ref=e5]:
    - generic [ref=e7]:
      - generic [ref=e8]: DocIntel
      - generic [ref=e9]: Vision Document Intelligence
    - navigation [ref=e10]:
      - link "Workspace" [ref=e11] [cursor=pointer]:
        - /url: /
        - img [ref=e13]
        - text: Workspace
      - link "Documents" [ref=e20] [cursor=pointer]:
        - /url: /documents
        - img [ref=e21]
        - text: Documents
      - link "Image Intelligence" [ref=e23] [cursor=pointer]:
        - /url: /images
        - img [ref=e24]
        - text: Image Intelligence
      - link "Mobile Scanner" [ref=e28] [cursor=pointer]:
        - /url: /camera
        - img [ref=e29]
        - text: Mobile Scanner
      - link "Pipelines" [ref=e32] [cursor=pointer]:
        - /url: /pipelines
        - img [ref=e33]
        - text: Pipelines
      - link "Compare Routes" [ref=e37] [cursor=pointer]:
        - /url: /compare
        - img [ref=e38]
        - text: Compare Routes
      - link "Batch" [ref=e45] [cursor=pointer]:
        - /url: /batch
        - img [ref=e46]
        - text: Batch
      - link "Benchmarks" [ref=e50] [cursor=pointer]:
        - /url: /benchmarks
        - img [ref=e51]
        - text: Benchmarks
      - link "Vision Models" [ref=e53] [cursor=pointer]:
        - /url: /models
        - img [ref=e54]
        - text: Vision Models
      - link "Activity" [ref=e57] [cursor=pointer]:
        - /url: /activity
        - img [ref=e58]
        - text: Activity
      - link "Settings" [ref=e62] [cursor=pointer]:
        - /url: /settings
        - img [ref=e63]
        - text: Settings
      - link "API Docs" [ref=e66] [cursor=pointer]:
        - /url: /api-docs
        - img [ref=e67]
        - text: API Docs
      - link "User Guide" [ref=e71] [cursor=pointer]:
        - /url: /user-guide
        - img [ref=e72]
        - text: User Guide
    - generic [ref=e74]: Backend online
  - main [ref=e77]:
    - generic [ref=e79]:
      - generic [ref=e81]:
        - heading "Good afternoon. Ready to analyze documents." [level=1] [ref=e82]
        - paragraph [ref=e83]: Upload a document. DocIntel classifies it, routes it to the right vision model, and returns structured, validated data.
      - generic [ref=e84]:
        - generic [ref=e85]:
          - generic [ref=e86]: Extraction route
          - generic [ref=e87]:
            - button "Claude Vision" [ref=e88] [cursor=pointer]: Claude Vision
            - button "Local Vision" [ref=e90] [cursor=pointer]
            - button "OCR + LLM" [ref=e91] [cursor=pointer]
        - generic [ref=e92]:
          - generic [ref=e93]: Document type
          - combobox [ref=e94]:
            - option "Auto-detect" [selected]
            - option "invoice"
            - option "receipt"
            - option "contract"
            - option "financial report"
            - option "default"
      - generic [ref=e96] [cursor=pointer]:
        - img [ref=e98]
        - generic [ref=e101]: Drop your document here
        - generic [ref=e102]: or click to browse — PDF · PNG · JPEG · TIFF
```

# Test source

```ts
  149 |     // Mock navigation to route containing ApiDocs
  150 |     await page.waitForLoadState('domcontentloaded');
  151 |     const rootHtml = await page.locator('#root').innerHTML();
  152 |     expect(rootHtml.length).toBeGreaterThan(0);
  153 |   });
  154 | 
  155 |   test('Should render and interact with Batch (pages/Batch.tsx)', async ({ page }) => {
  156 |     // Mock navigation to route containing Batch
  157 |     await page.goto(BASE_URL + '/docintel/batch');
  158 |     await page.waitForLoadState('domcontentloaded');
  159 |     const rootHtml = await page.locator('#root').innerHTML();
  160 |     expect(rootHtml.length).toBeGreaterThan(0);
  161 |   });
  162 | 
  163 |   test('Should render and interact with Settings (pages/Settings.tsx)', async ({ page }) => {
  164 |     // Mock navigation to route containing Settings
  165 |     await page.goto(BASE_URL + '/docintel/settings');
  166 |     await page.waitForLoadState('domcontentloaded');
  167 |     const rootHtml = await page.locator('#root').innerHTML();
  168 |     expect(rootHtml.length).toBeGreaterThan(0);
  169 |   });
  170 | 
  171 |   test('Should render and interact with Activity (pages/Activity.tsx)', async ({ page }) => {
  172 |     // Mock navigation to route containing Activity
  173 |     await page.goto(BASE_URL + '/docintel/activity');
  174 |     await page.waitForLoadState('domcontentloaded');
  175 |     const rootHtml = await page.locator('#root').innerHTML();
  176 |     expect(rootHtml.length).toBeGreaterThan(0);
  177 |   });
  178 | 
  179 | });
  180 | 
  181 | test.describe("2026 UI/UX Standards Validation", () => {
  182 |   test("Should verify haptic feedback scale animation on buttons", async ({ page }) => {
  183 |     await page.goto(BASE_URL);
  184 |     const btn = page.locator('button').first();
  185 |     if (await btn.isVisible()) {
  186 |       // Hover the button and simulate mouse down to trigger :active
  187 |       const box = await btn.boundingBox();
  188 |       if (box) {
  189 |         await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  190 |         await page.mouse.down();
  191 |         // The scale should drop to 0.96 due to the new CSS rules
  192 |         const transform = await btn.evaluate((el) => window.getComputedStyle(el).transform);
  193 |         // Note: transform is usually a matrix. We check that it's not 'none'.
  194 |         expect(transform).not.toBe('none');
  195 |         await page.mouse.up();
  196 |       }
  197 |     }
  198 |   });
  199 | 
  200 |   test("Should verify accessibility focus-visible rings", async ({ page }) => {
  201 |     await page.goto(BASE_URL);
  202 |     const input = page.locator('input').first();
  203 |     if (await input.isVisible()) {
  204 |       await input.focus();
  205 |       const outline = await input.evaluate((el) => window.getComputedStyle(el).outline);
  206 |       // We expect the focus-visible to trigger either a box-shadow or an outline
  207 |       expect(outline).not.toBe('none');
  208 |     }
  209 |   });
  210 | });
  211 | 
  212 | test.describe("Mobile & Low-Bandwidth Resilience (Sahel Optimized)", () => {
  213 |   test("Should verify strict mobile viewport configuration", async ({ page }) => {
  214 |     await page.goto(BASE_URL);
  215 |     const viewport = await page.locator('meta[name="viewport"]').getAttribute('content');
  216 |     expect(viewport).toContain('width=device-width');
  217 |     expect(viewport).toContain('shrink-to-fit=no');
  218 |     expect(viewport).toContain('maximum-scale=5.0');
  219 |   });
  220 | 
  221 |   test("Should verify offline Service Worker registration", async ({ page }) => {
  222 |     await page.goto(BASE_URL);
  223 |     // Wait for window.onload so SW registers
  224 |     await page.waitForLoadState('domcontentloaded');
  225 |     
  226 |     // Evaluate if a service worker is registered in the navigator
  227 |     const isSwRegistered = await page.evaluate(async () => {
  228 |       if (!('serviceWorker' in navigator)) return false;
  229 |       const registrations = await navigator.serviceWorker.getRegistrations();
  230 |       return registrations.length > 0;
  231 |     });
  232 |     
  233 |     expect(isSwRegistered).toBe(true);
  234 |   });
  235 | 
  236 |   test("Should verify Service Worker uses Network-First strategy for documents to prevent stale cache", async ({ page }) => {
  237 |     // Intercept network requests to verify the SW doesn't block the document fetch
  238 |     let documentFetchedFromNetwork = false;
  239 |     page.on('request', request => {
  240 |       if (request.resourceType() === 'document' && request.url() === '/' + '/') {
  241 |         documentFetchedFromNetwork = true;
  242 |       }
  243 |     });
  244 |     
  245 |     await page.goto(BASE_URL);
  246 |     await page.waitForLoadState('domcontentloaded');
  247 |     
  248 |     // Evaluate the active Service Worker state to ensure it skips waiting
> 249 |     const swState = await page.evaluate(async () => {
      |                                ^ Error: page.evaluate: Test timeout of 45000ms exceeded.
  250 |       const reg = await navigator.serviceWorker.ready;
  251 |       return reg.active ? reg.active.state : 'none';
  252 |     });
  253 |     
  254 |     expect(['activated', 'activating']).toContain(swState);
  255 |   });
  256 | });
  257 | 
```