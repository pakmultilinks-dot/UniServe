import { getCafeterias } from "../services/data";
jest.mock("../services/api", () => {
  const { ApiClient, ApiClientError } = jest.requireActual("@uniserve/shared-types");
  return { ApiClientError, apiClient: new ApiClient("https://qa.example/api/v1", {
    getAccessToken: () => null, getRefreshToken: () => null, setTokens: jest.fn(), clearTokens: jest.fn(),
  }) };
});
it("recovers when the backend becomes available after the first 60-second read timeout", async () => {
  jest.useFakeTimers();
  const originalFetch = globalThis.fetch;
  const readyAt = Date.now() + 83000;
  const aborted = jest.fn();
  const fetchMock = jest.fn((_url: unknown, options: RequestInit | undefined) => new Promise<Response>((resolve, reject) => {
    const timer = setTimeout(() => resolve({
      ok: true, status: 200,
      headers: { get: () => null },
      json: async () => ({ cafeterias: [{ id: "awake-cafeteria" }] }),
    } as unknown as Response), Math.max(0, readyAt - Date.now()));
    options?.signal?.addEventListener("abort", () => {
      clearTimeout(timer); aborted();
      const error = new Error("aborted"); error.name = "AbortError"; reject(error);
    });
  }));
  globalThis.fetch = fetchMock as typeof fetch;
  try {
    const pending = getCafeterias();
    await jest.advanceTimersByTimeAsync(83001);
    expect(await pending).toEqual([{ id: "awake-cafeteria" }]);
    expect(aborted).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls.every(([url]) => url === "https://qa.example/api/v1/cafeterias/?is_active=true")).toBe(true);
  } finally { globalThis.fetch = originalFetch; jest.useRealTimers(); }
});
