/**
 * ApiClient — Session Restoration Regression Tests
 *
 * Covers the defect where `response.status === 401 && token`
 * prevented refresh when access token was absent (page reload).
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { ApiClient, ApiClientError } from "../index";
import type { TokenProvider, TokenPair } from "../index";

// ---- Helpers ----

/**
 * Mock Response that works in Node.js / vitest.
 * Captures headers by value at construction time so assertions
 * are not affected by later in-place mutations by the ApiClient.
 */
function mockResponse(
  body: unknown,
  status: number,
): Response {
  const bodyText = JSON.stringify(body);
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Map([["content-type", "application/json"]]),
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(bodyText),
    clone: function () { return mockResponse(body, status); },
  } as unknown as Response;
}

function createMockTokenProvider(
  overrides: Partial<{
    accessToken: string | null;
    refreshToken: string | null;
  }> = {},
) {
  const state = {
    _access: overrides.accessToken ?? null,
    _refresh: overrides.refreshToken ?? null,
  };

  return {
    getAccessToken: () => state._access,
    getRefreshToken: () => state._refresh,
    setTokens: vi.fn((access: string, refresh: string) => {
      state._access = access;
      state._refresh = refresh;
    }),
    clearTokens: vi.fn(() => {
      state._access = null;
      state._refresh = null;
    }),
  };
}

const TOKEN_PAIR: TokenPair = {
  access_token: "new-access-token",
  refresh_token: "new-refresh-token",
  token_type: "bearer",
  expires_in: 1800,
};

const USER_DATA = { id: "u1", email: "test@lgu.edu.pk", role: "student" };

// ---- Tests ----

describe("ApiClient.request() — session restoration", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // Case 1: Access token exists → API returns 401 → refresh → retry succeeds
  it("Case 1: refreshes when access token exists but is expired", async () => {
    const provider = createMockTokenProvider({
      accessToken: "expired-token",
      refreshToken: "valid-refresh-token",
    });
    const client = new ApiClient("http://api.test/v1", provider);

    // Capture headers at call time by cloning the headers object
    const capturedHeaders: Array<Record<string, string | undefined>> = [];
    fetchSpy.mockImplementation(async (_url: string, opts?: { headers?: Record<string, string> }) => {
      capturedHeaders.push({ Authorization: opts?.headers?.Authorization });
      const idx = capturedHeaders.length;
      if (idx === 1) return mockResponse({ detail: "Unauthorized" }, 401);
      if (idx === 2) return mockResponse(TOKEN_PAIR, 200);
      return mockResponse(USER_DATA, 200);
    });

    const result = await client.get("/auth/me");

    expect(result).toEqual(USER_DATA);
    expect(fetchSpy).toHaveBeenCalledTimes(3);
    // First call: with expired token
    expect(capturedHeaders[0].Authorization).toBe("Bearer expired-token");
    // Refresh call
    expect(fetchSpy.mock.calls[1][0]).toBe("http://api.test/v1/auth/refresh");
    // Retry call: with new token
    expect(capturedHeaders[2].Authorization).toBe("Bearer new-access-token");
    // Tokens were updated
    expect(provider.setTokens).toHaveBeenCalledWith(
      "new-access-token",
      "new-refresh-token",
    );
  });

  // Case 2: Access token absent but refresh token exists → 401 → refresh → retry succeeds
  it("Case 2: refreshes when access token is absent but refresh token exists (page reload)", async () => {
    const provider = createMockTokenProvider({
      accessToken: null,
      refreshToken: "refresh-from-session-storage",
    });
    const client = new ApiClient("http://api.test/v1", provider);

    const capturedHeaders: Array<Record<string, string | undefined>> = [];
    const capturedBodies: Array<string | undefined> = [];
    fetchSpy.mockImplementation(async (_url: string, opts?: { headers?: Record<string, string>; body?: string }) => {
      capturedHeaders.push({ Authorization: opts?.headers?.Authorization });
      capturedBodies.push(opts?.body);
      const idx = capturedHeaders.length;
      if (idx === 1) return mockResponse({ detail: "Unauthorized" }, 401);
      if (idx === 2) return mockResponse(TOKEN_PAIR, 200);
      return mockResponse(USER_DATA, 200);
    });

    const result = await client.get("/auth/me");

    expect(result).toEqual(USER_DATA);
    expect(fetchSpy).toHaveBeenCalledTimes(3);
    // First call: no Authorization header
    expect(capturedHeaders[0].Authorization).toBeUndefined();
    // Refresh call with the stored refresh token
    const refreshBody = JSON.parse(capturedBodies[1]!);
    expect(refreshBody.refresh_token).toBe("refresh-from-session-storage");
    // Retry call: with new token
    expect(capturedHeaders[2].Authorization).toBe("Bearer new-access-token");
    expect(provider.setTokens).toHaveBeenCalledWith(
      "new-access-token",
      "new-refresh-token",
    );
  });

  // Case 3: Access token absent + no refresh token → authentication failure
  it("Case 3: throws auth error when no tokens exist", async () => {
    const provider = createMockTokenProvider({
      accessToken: null,
      refreshToken: null,
    });
    const client = new ApiClient("http://api.test/v1", provider);

    fetchSpy.mockResolvedValueOnce(mockResponse({ detail: "Unauthorized" }, 401));

    try {
      await client.get("/auth/me");
      expect.fail("Should have thrown");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiClientError);
      expect((err as ApiClientError).status).toBe(401);
    }

    // Only 1 fetch call — no refresh attempted
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    // No token operations
    expect(provider.setTokens).not.toHaveBeenCalled();
    expect(provider.clearTokens).not.toHaveBeenCalled();
  });

  // Case 4: Refresh fails → tokens cleared → auth failure invoked
  it("Case 4: clears tokens and invokes onAuthFailure when refresh fails", async () => {
    const provider = createMockTokenProvider({
      accessToken: "expired-token",
      refreshToken: "bad-refresh-token",
    });
    const onAuthFailure = vi.fn();
    const client = new ApiClient(
      "http://api.test/v1",
      provider,
      onAuthFailure,
    );

    // First request → 401, refresh → 401 (bad refresh token)
    fetchSpy
      .mockResolvedValueOnce(mockResponse({ detail: "Unauthorized" }, 401))
      .mockResolvedValueOnce(mockResponse({ detail: "Invalid refresh token" }, 401));

    try {
      await client.get("/auth/me");
      expect.fail("Should have thrown");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiClientError);
      expect((err as ApiClientError).status).toBe(401);
    }

    // Refresh was attempted
    expect(fetchSpy).toHaveBeenCalledTimes(2);
    // Tokens cleared
    expect(provider.clearTokens).toHaveBeenCalled();
    // Auth failure callback invoked
    expect(onAuthFailure).toHaveBeenCalled();
  });

  // Case 5: Concurrent 401 requests share one refresh operation
  it("Case 5: deduplicates concurrent refresh requests via refreshPromise", async () => {
    const provider = createMockTokenProvider({
      accessToken: "expired-token",
      refreshToken: "valid-refresh-token",
    });
    const client = new ApiClient("http://api.test/v1", provider);

    let callCount = 0;
    fetchSpy.mockImplementation(async () => {
      callCount++;
      if (callCount <= 3) {
        // First 3 calls: initial requests from concurrent callers → 401
        return mockResponse({ detail: "Unauthorized" }, 401);
      }
      if (callCount === 4) {
        // 4th call: the single shared refresh request
        return mockResponse(TOKEN_PAIR, 200);
      }
      // Calls 5-7: retries after refresh
      return mockResponse(USER_DATA, 200);
    });

    const results = await Promise.all([
      client.get("/users/1"),
      client.get("/users/2"),
      client.get("/users/3"),
    ]);

    expect(results).toEqual([USER_DATA, USER_DATA, USER_DATA]);
    // 3 initial 401s + 1 refresh + 3 retries = 7 total
    expect(fetchSpy).toHaveBeenCalledTimes(7);
    // setTokens called only once (deduplication)
    expect(provider.setTokens).toHaveBeenCalledTimes(1);
  });

  // Case 6: Refresh retry does not create an infinite loop
  it("Case 6: retry after refresh does not loop infinitely even if retry also 401s", async () => {
    const provider = createMockTokenProvider({
      accessToken: "expired-token",
      refreshToken: "valid-refresh-token",
    });
    const client = new ApiClient("http://api.test/v1", provider);

    // 401 → refresh succeeds → retry also returns 401 → should throw, not loop
    fetchSpy
      .mockResolvedValueOnce(mockResponse({ detail: "Unauthorized" }, 401))
      .mockResolvedValueOnce(mockResponse(TOKEN_PAIR, 200))
      .mockResolvedValueOnce(mockResponse({ detail: "Still unauthorized" }, 401));

    try {
      await client.get("/protected");
      expect.fail("Should have thrown");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiClientError);
      expect((err as ApiClientError).status).toBe(401);
    }

    // Exactly 3 fetches: initial + refresh + retry (no infinite loop)
    expect(fetchSpy).toHaveBeenCalledTimes(3);
  });
});

describe("ApiClient.request() — happy paths", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("sends Authorization header when access token exists", async () => {
    const provider = createMockTokenProvider({
      accessToken: "my-token",
      refreshToken: "my-refresh",
    });
    const client = new ApiClient("http://api.test/v1", provider);

    const capturedHeaders: Array<Record<string, string | undefined>> = [];
    fetchSpy.mockImplementation(async (_url: string, opts?: { headers?: Record<string, string> }) => {
      capturedHeaders.push({ Authorization: opts?.headers?.Authorization });
      return mockResponse(USER_DATA, 200);
    });

    const result = await client.get("/auth/me");

    expect(result).toEqual(USER_DATA);
    expect(capturedHeaders[0].Authorization).toBe("Bearer my-token");
  });

  it("does not send Authorization header when access token is absent", async () => {
    const provider = createMockTokenProvider({
      accessToken: null,
      refreshToken: "my-refresh",
    });
    const client = new ApiClient("http://api.test/v1", provider);

    const capturedHeaders: Array<Record<string, string | undefined>> = [];
    fetchSpy.mockImplementation(async (_url: string, opts?: { headers?: Record<string, string> }) => {
      capturedHeaders.push({ Authorization: opts?.headers?.Authorization });
      return mockResponse({ message: "ok" }, 200);
    });

    await client.get("/public");

    expect(capturedHeaders[0].Authorization).toBeUndefined();
  });

  it("throws ApiClientError on non-401 errors without attempting refresh", async () => {
    const provider = createMockTokenProvider({
      accessToken: "my-token",
      refreshToken: "my-refresh",
    });
    const client = new ApiClient("http://api.test/v1", provider);

    fetchSpy.mockResolvedValueOnce(
      mockResponse({ detail: "Not found" }, 404),
    );

    try {
      await client.get("/missing");
      expect.fail("Should have thrown");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiClientError);
      expect((err as ApiClientError).status).toBe(404);
    }

    // Only 1 fetch — no refresh attempted
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });
});
