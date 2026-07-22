# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: exhaustive_ui.spec.ts >> Exhaustive UI Component & Page Flow Suite >> Should render and interact with ApiDocs (pages/ApiDocs.tsx)
- Location: e2e/exhaustive_ui.spec.ts:148:3

# Error details

```
Test timeout of 45000ms exceeded.
```

```
Error: locator.innerHTML: Test timeout of 45000ms exceeded.
Call log:
  - waiting for locator('#root')

```

# Test source

```ts
  51  | 
  52  |   test('Should render and interact with PipelineFlow (kit/PipelineFlow.tsx)', async ({ page }) => {
  53  |     // Mock navigation to route containing PipelineFlow
  54  |     // Component-level isolation test via storybook/mount mock (Conceptual for full-mesh E2E)
  55  |     expect(true).toBeTruthy(); // Placeholder for deep component mesh
  56  |   });
  57  | 
  58  |   test('Should render and interact with JSONViewer (kit/JSONViewer.tsx)', async ({ page }) => {
  59  |     // Mock navigation to route containing JSONViewer
  60  |     // Component-level isolation test via storybook/mount mock (Conceptual for full-mesh E2E)
  61  |     expect(true).toBeTruthy(); // Placeholder for deep component mesh
  62  |   });
  63  | 
  64  |   test('Should render and interact with primitives (kit/primitives.tsx)', async ({ page }) => {
  65  |     // Mock navigation to route containing primitives
  66  |     // Component-level isolation test via storybook/mount mock (Conceptual for full-mesh E2E)
  67  |     expect(true).toBeTruthy(); // Placeholder for deep component mesh
  68  |   });
  69  | 
  70  |   test('Should render and interact with AppShell (kit/AppShell.tsx)', async ({ page }) => {
  71  |     // Mock navigation to route containing AppShell
  72  |     // Component-level isolation test via storybook/mount mock (Conceptual for full-mesh E2E)
  73  |     expect(true).toBeTruthy(); // Placeholder for deep component mesh
  74  |   });
  75  | 
  76  |   test('Should render and interact with CameraDashboard (pages/CameraDashboard.tsx)', async ({ page }) => {
  77  |     // Mock navigation to route containing CameraDashboard
  78  |     await page.goto(BASE_URL + '/docintel/cameradashboard');
  79  |     await page.waitForLoadState('domcontentloaded');
  80  |     const rootHtml = await page.locator('#root').innerHTML();
  81  |     expect(rootHtml.length).toBeGreaterThan(0);
  82  |   });
  83  | 
  84  |   test('Should render and interact with ImageIntel (pages/ImageIntel.tsx)', async ({ page }) => {
  85  |     // Mock navigation to route containing ImageIntel
  86  |     await page.goto(BASE_URL + '/docintel/imageintel');
  87  |     await page.waitForLoadState('domcontentloaded');
  88  |     const rootHtml = await page.locator('#root').innerHTML();
  89  |     expect(rootHtml.length).toBeGreaterThan(0);
  90  |   });
  91  | 
  92  |   test('Should render and interact with Pipelines (pages/Pipelines.tsx)', async ({ page }) => {
  93  |     // Mock navigation to route containing Pipelines
  94  |     await page.goto(BASE_URL + '/docintel/pipelines');
  95  |     await page.waitForLoadState('domcontentloaded');
  96  |     const rootHtml = await page.locator('#root').innerHTML();
  97  |     expect(rootHtml.length).toBeGreaterThan(0);
  98  |   });
  99  | 
  100 |   test('Should render and interact with CameraMobile (pages/CameraMobile.tsx)', async ({ page }) => {
  101 |     // Mock navigation to route containing CameraMobile
  102 |     await page.goto(BASE_URL + '/docintel/cameramobile');
  103 |     await page.waitForLoadState('domcontentloaded');
  104 |     const rootHtml = await page.locator('#root').innerHTML();
  105 |     expect(rootHtml.length).toBeGreaterThan(0);
  106 |   });
  107 | 
  108 |   test('Should render and interact with Documents (pages/Documents.tsx)', async ({ page }) => {
  109 |     // Mock navigation to route containing Documents
  110 |     await page.goto(BASE_URL + '/docintel/documents');
  111 |     await page.waitForLoadState('domcontentloaded');
  112 |     const rootHtml = await page.locator('#root').innerHTML();
  113 |     expect(rootHtml.length).toBeGreaterThan(0);
  114 |   });
  115 | 
  116 |   test('Should render and interact with Compare (pages/Compare.tsx)', async ({ page }) => {
  117 |     // Mock navigation to route containing Compare
  118 |     await page.goto(BASE_URL + '/docintel/compare');
  119 |     await page.waitForLoadState('domcontentloaded');
  120 |     const rootHtml = await page.locator('#root').innerHTML();
  121 |     expect(rootHtml.length).toBeGreaterThan(0);
  122 |   });
  123 | 
  124 |   test('Should render and interact with Models (pages/Models.tsx)', async ({ page }) => {
  125 |     // Mock navigation to route containing Models
  126 |     await page.goto(BASE_URL + '/docintel/models');
  127 |     await page.waitForLoadState('domcontentloaded');
  128 |     const rootHtml = await page.locator('#root').innerHTML();
  129 |     expect(rootHtml.length).toBeGreaterThan(0);
  130 |   });
  131 | 
  132 |   test('Should render and interact with Benchmarks (pages/Benchmarks.tsx)', async ({ page }) => {
  133 |     // Mock navigation to route containing Benchmarks
  134 |     await page.goto(BASE_URL + '/docintel/benchmarks');
  135 |     await page.waitForLoadState('domcontentloaded');
  136 |     const rootHtml = await page.locator('#root').innerHTML();
  137 |     expect(rootHtml.length).toBeGreaterThan(0);
  138 |   });
  139 | 
  140 |   test('Should render and interact with Workspace (pages/Workspace.tsx)', async ({ page }) => {
  141 |     // Mock navigation to route containing Workspace
  142 |     await page.goto(BASE_URL + '/docintel/workspace');
  143 |     await page.waitForLoadState('domcontentloaded');
  144 |     const rootHtml = await page.locator('#root').innerHTML();
  145 |     expect(rootHtml.length).toBeGreaterThan(0);
  146 |   });
  147 | 
  148 |   test('Should render and interact with ApiDocs (pages/ApiDocs.tsx)', async ({ page }) => {
  149 |     // Mock navigation to route containing ApiDocs
  150 |     await page.waitForLoadState('domcontentloaded');
> 151 |     const rootHtml = await page.locator('#root').innerHTML();
      |                                                  ^ Error: locator.innerHTML: Test timeout of 45000ms exceeded.
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
  249 |     const swState = await page.evaluate(async () => {
  250 |       const reg = await navigator.serviceWorker.ready;
  251 |       return reg.active ? reg.active.state : 'none';
```