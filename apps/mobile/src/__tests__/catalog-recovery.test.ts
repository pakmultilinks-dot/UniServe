import { ApiClientError, apiClient } from "../services/api";
import { getCafeterias, getTodaysMenu, checkoutCart } from "../services/data";
jest.mock("../services/api", () => ({
  ApiClientError: jest.requireActual("@uniserve/shared-types").ApiClientError,
  apiClient: { request: jest.fn(), post: jest.fn() },
}));
const request = apiClient.request as jest.Mock;
beforeEach(() => { jest.useFakeTimers(); jest.resetAllMocks(); });
afterEach(() => { jest.useRealTimers(); });

it.each([0, 408, 502, 503, 504])("recovers a transient catalog failure %s once", async (status) => {
  request.mockRejectedValueOnce(new ApiClientError(status, "temporary"))
    .mockResolvedValueOnce({ cafeterias: [{ id: "c1" }] });
  const pending = getCafeterias();
  await jest.advanceTimersByTimeAsync(1000);
  expect(await pending).toEqual([{ id: "c1" }]);
  expect(request).toHaveBeenCalledTimes(2);
});
it("stops after the second failed read and permits a later user retry", async () => {
  request.mockRejectedValue(new ApiClientError(503, "unavailable"));
  const pending = expect(getCafeterias()).rejects.toThrow("unavailable");
  await jest.advanceTimersByTimeAsync(1000); await pending;
  expect(request).toHaveBeenCalledTimes(2);
  request.mockResolvedValueOnce({ cafeterias: [{ id: "recovered" }] });
  expect(await getCafeterias()).toEqual([{ id: "recovered" }]);
});
it.each([401, 403, 404, 422])("does not retry permanent rejection %s", async (status) => {
  request.mockRejectedValue(new ApiClientError(status, "rejected"));
  await expect(getCafeterias()).rejects.toThrow("rejected");
  expect(request).toHaveBeenCalledTimes(1);
});
it("also retries a failed published-menu read", async () => {
  request.mockRejectedValueOnce(new ApiClientError(503, "waking"))
    .mockResolvedValueOnce({ items: [] });
  const pending = getTodaysMenu("c1");
  await jest.advanceTimersByTimeAsync(1000);
  expect(await pending).toEqual({ items: [] });
});
it("never replays a checkout mutation after network failure", async () => {
  (apiClient.post as jest.Mock).mockRejectedValueOnce(new ApiClientError(0, "offline"));
  await expect(checkoutCart("c1", { payment_method: "cash" })).rejects.toThrow("offline");
  expect(apiClient.post).toHaveBeenCalledTimes(1);
  expect(request).not.toHaveBeenCalled();
});
