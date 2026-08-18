import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Regression tests for two frontend audit findings fixed this session:
//   - api.ts retried ALL methods (including POST) on 5xx/network failure,
//     risking a duplicate paid vision/LLM call or duplicate batch job
//   - VITE_DOCINTEL_INTERNAL_TOKEN was never actually sent by the shipped
//     UI, so enabling the backend's REQUIRE_INTERNAL_TOKEN hardening broke
//     the app's own requests to itself
//
// Both live in api.ts's shared req() helper, not in any React component, so
// these are pure-logic tests against a mocked global.fetch — no DOM/jsdom
// needed.

describe('api.ts req() — mutating-request retry safety', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it('does not retry a POST on a 500 response', async () => {
    const { api, ApiError } = await import('../src/lib/api');
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: 'boom' }), { status: 500 }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const file = new File([new Uint8Array([1, 2, 3])], 'a.png', { type: 'image/png' });
    await expect(api.process(file, 'vision_route_a', 'auto')).rejects.toBeInstanceOf(ApiError);

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('does not retry a POST on a network failure (TypeError)', async () => {
    const { api } = await import('../src/lib/api');
    const fetchMock = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'));
    vi.stubGlobal('fetch', fetchMock);

    const file = new File([new Uint8Array([1, 2, 3])], 'a.png', { type: 'image/png' });
    await expect(api.process(file, 'vision_route_a', 'auto')).rejects.toThrow();

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('does retry a GET on a 500 response', async () => {
    const { api } = await import('../src/lib/api');
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response('err', { status: 500 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ status: 'ok', service: 'docintel', version: '1' }), { status: 200 }),
      );
    vi.stubGlobal('fetch', fetchMock);

    const promise = api.health();
    await vi.runAllTimersAsync();
    const result = await promise;

    expect(result.status).toBe('ok');
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});

describe('api.ts req() — internal token header attachment', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
    vi.resetModules();
  });

  it('attaches X-DocIntel-Internal-Token when VITE_DOCINTEL_INTERNAL_TOKEN is set at build time', async () => {
    vi.stubEnv('VITE_DOCINTEL_INTERNAL_TOKEN', 'secret-abc');
    vi.resetModules();
    const { api } = await import('../src/lib/api');

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: 'ok', service: 'docintel', version: '1' }), { status: 200 }),
    );
    vi.stubGlobal('fetch', fetchMock);

    await api.health();

    const [, init] = fetchMock.mock.calls[0];
    const headers = new Headers(init.headers);
    expect(headers.get('X-DocIntel-Internal-Token')).toBe('secret-abc');
  });

  it('omits the header entirely when no token is configured', async () => {
    vi.stubEnv('VITE_DOCINTEL_INTERNAL_TOKEN', '');
    vi.resetModules();
    const { api } = await import('../src/lib/api');

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: 'ok', service: 'docintel', version: '1' }), { status: 200 }),
    );
    vi.stubGlobal('fetch', fetchMock);

    await api.health();

    const [, init] = fetchMock.mock.calls[0];
    const headers = new Headers(init.headers);
    expect(headers.has('X-DocIntel-Internal-Token')).toBe(false);
  });
});
