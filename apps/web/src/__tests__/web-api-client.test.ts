/**
 * Phase 60 (Workstream A) — Web API wrapper behaviour tests.
 *
 * Asserts the token lifecycle and query-shaping behaviour of the web
 * `lib/api` wrappers through a fetch-mocked ApiClient. Module-scope token
 * state is reset between tests by calling `logout()` (its `finally` clears
 * local tokens even when the server call fails).
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as webApi from "@/lib/api";

function mockResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as unknown as Response;
}

const USER = {
  id: "u1",
  role: "cafeteria_manager",
  first_name: "Ayesha",
  last_name: "Khan",
  university_email: "ayesha.khan@lgu.edu.pk",
};

const TOKENS = {
  access_token: "access-1",
  refresh_token: "refresh-1",
  token_type: "bearer",
  expires_in: 1800,
};

const fetchSpy = vi.fn();

async function loginOnce(): Promise<void> {
  fetchSpy.mockResolvedValueOnce(mockResponse({ user: USER, tokens: TOKENS }));
  await webApi.login({
    university_email: "ayesha.khan@lgu.edu.pk",
    password: "StrongPass1!",
  });
}

beforeEach(() => {
  vi.stubGlobal("fetch", fetchSpy);
  fetchSpy.mockReset();
  sessionStorage.clear();
});

afterEach(async () => {
  // Reset module-scope token state: clearTokens runs in logout()'s finally.
  fetchSpy.mockResolvedValue(mockResponse({}));
  await webApi.logout().catch(() => undefined);
  sessionStorage.clear();
  vi.unstubAllGlobals();
});

describe("web api — token lifecycle", () => {
  it("login stores tokens; later requests carry the access token", async () => {
    await loginOnce();

    expect(sessionStorage.getItem("uniserve_refresh_token")).toBe("refresh-1");

    fetchSpy.mockResolvedValueOnce(mockResponse(USER));
    await webApi.getCurrentUser();

    const [, init] = fetchSpy.mock.calls.at(-1)!;
    expect((init as { headers: Record<string, string> }).headers.Authorization).toBe(
      "Bearer access-1",
    );
  });

  it("login sets the lightweight session flag cookie", async () => {
    await loginOnce();
    expect(document.cookie).toContain("uniserve_session=1");
  });

  it("refreshTokens rotates the stored refresh token", async () => {
    await loginOnce();

    fetchSpy.mockResolvedValueOnce(
      mockResponse({
        access_token: "access-2",
        refresh_token: "refresh-2",
        token_type: "bearer",
        expires_in: 1800,
      }),
    );
    const pair = await webApi.refreshTokens();

    expect(pair.access_token).toBe("access-2");
    expect(sessionStorage.getItem("uniserve_refresh_token")).toBe("refresh-2");

    const refreshCall = fetchSpy.mock.calls.find(([url]) =>
      String(url).endsWith("/auth/refresh"),
    );
    expect(refreshCall).toBeDefined();
    const body = JSON.parse((refreshCall![1] as { body: string }).body);
    expect(body.refresh_token).toBe("refresh-1");
  });

  it("refreshTokens fails clearly when no refresh token is stored", async () => {
    await expect(webApi.refreshTokens()).rejects.toThrow(/no refresh token/i);
  });

  it("logout clears local tokens even when the server call fails", async () => {
    await loginOnce();
    expect(sessionStorage.getItem("uniserve_refresh_token")).toBe("refresh-1");

    fetchSpy.mockRejectedValueOnce(new Error("server unreachable"));
    // The wrapper propagates the server error but still clears local tokens
    // in its finally block (AuthContext swallows it at a higher layer).
    await expect(webApi.logout()).rejects.toThrow("server unreachable");
    expect(sessionStorage.getItem("uniserve_refresh_token")).toBeNull();
  });
});

describe("web api — query shaping", () => {
  it("getMyCafeterias falls back to [] when the endpoint fails", async () => {
    fetchSpy.mockRejectedValueOnce(new Error("boom"));
    await expect(webApi.getMyCafeterias()).resolves.toEqual([]);
  });

  it("getMyCafeterias returns assigned ids on success", async () => {
    fetchSpy.mockResolvedValueOnce(mockResponse({ cafeteria_ids: ["c1", "c2"] }));
    await expect(webApi.getMyCafeterias()).resolves.toEqual(["c1", "c2"]);
  });

  it("getCafeterias adds is_active only when requested", async () => {
    fetchSpy.mockResolvedValueOnce(mockResponse({ cafeterias: [{ id: "c1" }] }));
    await webApi.getCafeterias({ isActive: true });
    expect(String(fetchSpy.mock.calls[0][0])).toContain(
      "/cafeterias?is_active=true",
    );

    fetchSpy.mockResolvedValueOnce(mockResponse({ cafeterias: [] }));
    await webApi.getCafeterias();
    expect(String(fetchSpy.mock.calls[1][0])).toBe(
      "http://localhost:8000/api/v1/cafeterias",
    );
  });

  it("getOrders unwraps the envelope and forwards the status filter", async () => {
    fetchSpy.mockResolvedValueOnce(
      mockResponse({ orders: [{ id: "o1" }], total: 1 }),
    );
    const orders = await webApi.getOrders({ status: "ready" });
    expect(orders).toEqual([{ id: "o1" }]);
    expect(String(fetchSpy.mock.calls[0][0])).toContain("/orders?status=ready");
  });
});

describe("web login delayed-backend recovery", () => {
  it("waits through the observed83-second production response", async () => {
    vi.useFakeTimers();
    fetchSpy.mockImplementationOnce((_url, init: RequestInit) => new Promise((resolve, reject) => {
      const timer = setTimeout(() => resolve(mockResponse({ user: USER, tokens: TOKENS })),83000);
      init.signal?.addEventListener("abort", () => { clearTimeout(timer); const error = new Error("aborted"); error.name = "AbortError"; reject(error); });
    }));
    try {
      const pending = webApi.login({ university_email: USER.university_email, password: "TestOnlyPass1!" });
      await vi.advanceTimersByTimeAsync(83000);
      expect((await pending).tokens.access_token).toBe(TOKENS.access_token);
      expect(fetchSpy).toHaveBeenCalledTimes(1);
    } finally { vi.useRealTimers(); }
  });
  it("still times out a stalled login and never replays it automatically", async () => {
    vi.useFakeTimers();
    fetchSpy.mockImplementationOnce((_url, init: RequestInit) => new Promise((_resolve, reject) => {
      init.signal?.addEventListener("abort", () => { const error = new Error("aborted"); error.name = "AbortError"; reject(error); });
    }));
    try {
      const pending = expect(webApi.login({ university_email: USER.university_email, password: "TestOnlyPass1!" })).rejects.toThrow("Request timed out");
      await vi.advanceTimersByTimeAsync(125001); await pending;
      expect(fetchSpy).toHaveBeenCalledTimes(1);
    } finally { vi.useRealTimers(); }
  });
});

it("restores the current user through an83-second delayed backend response", async () => {
  vi.useFakeTimers();
  fetchSpy.mockImplementationOnce((_url, init: RequestInit) => new Promise((resolve, reject) => {
    const timer = setTimeout(() => resolve(mockResponse(USER)),83000);
    init.signal?.addEventListener("abort", () => { clearTimeout(timer); const error = new Error("aborted"); error.name = "AbortError"; reject(error); });
  }));
  try {
    const pending = webApi.getCurrentUser();
    await vi.advanceTimersByTimeAsync(83000);
    expect((await pending).id).toBe(USER.id);
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  } finally { vi.useRealTimers(); }
});
