/**
 * Phase 60 (Workstream B) — Mobile data-service contract tests.
 *
 * Asserts the observable API contracts of the ordering path: active-only
 * cafeteria queries, cart checkout defaults, owner-scoped refund requests
 * with idempotency keys, and the notification helpers.
 */

jest.mock("../services/api", () => ({
  ApiClientError: jest.requireActual("@uniserve/shared-types").ApiClientError,
  apiClient: {
    request: jest.fn(),
    get: jest.fn(),
    post: jest.fn(),
    patch: jest.fn(),
    delete: jest.fn(),
  },
}));

import { apiClient } from "../services/api";
import {
  getCafeterias,
  checkoutCart,
  requestRefund,
  getNotificationsPage,
  getUnreadNotificationCount,
  markNotificationRead,
  markAllNotificationsRead,
} from "../services/data";

const apiMock = apiClient as jest.Mocked<typeof apiClient>;

beforeEach(() => {
  jest.clearAllMocks();
});

describe("data service — cafeterias", () => {
  it("requests active-only cafeterias for the customer ordering path", async () => {
    apiMock.request.mockResolvedValue({ cafeterias: [{ id: "c1" }], total: 1 });

    const result = await getCafeterias();

    // The backend route is GET /cafeterias/ (trailing slash) — FastAPI
    // 307-redirects the non-slash form, but the client hits the canonical
    // path directly to avoid the extra round-trip.
    expect(apiMock.request).toHaveBeenCalledWith("GET", "/cafeterias/?is_active=true", { timeout: 60000 });
    expect(result).toEqual([{ id: "c1" }]);
  });

  it("returns an empty list when the payload omits cafeterias", async () => {
    apiMock.request.mockResolvedValue({ total: 0 });

    expect(await getCafeterias()).toEqual([]);
  });
});

describe("data service — cart checkout (ordering)", () => {
  it("posts cash/immediate defaults to the cart checkout endpoint", async () => {
    apiMock.post.mockResolvedValue({ id: "o1" });

    await checkoutCart("c1", {});

    expect(apiMock.post).toHaveBeenCalledWith(
      "/cafeterias/c1/cart/checkout",
      { payment_method: "cash", order_type: "immediate" },
    );
  });

  it("forwards scheduling, note, and idempotency key when provided", async () => {
    apiMock.post.mockResolvedValue({ id: "o2" });

    await checkoutCart("c1", {
      payment_method: "online",
      order_type: "scheduled",
      scheduled_collection_time: "2025-06-01T12:00:00Z",
      note: "no onions",
      idempotency_key: "key-1",
    });

    expect(apiMock.post).toHaveBeenCalledWith(
      "/cafeterias/c1/cart/checkout",
      {
        payment_method: "online",
        order_type: "scheduled",
        scheduled_collection_time: "2025-06-01T12:00:00Z",
        note: "no onions",
        idempotency_key: "key-1",
      },
    );
  });
});

describe("data service — refund requests", () => {
  it("posts to the owner-scoped endpoint with an idempotency key", async () => {
    apiMock.post.mockResolvedValue({ id: "r1" });

    await requestRefund("o1", {
      amount: 250,
      reason: "item_unavailable",
      idempotency_key: "key-1",
    });

    expect(apiMock.post).toHaveBeenCalledWith("/refunds?order_id=o1", {
      amount: 250,
      reason: "item_unavailable",
      reason_note: null,
      idempotency_key: "key-1",
    });
  });

  it("forwards the reason note when provided", async () => {
    apiMock.post.mockResolvedValue({ id: "r2" });

    await requestRefund("o1", {
      amount: 100,
      reason: "other",
      reason_note: "item arrived cold",
      idempotency_key: "key-2",
    });

    expect(apiMock.post).toHaveBeenCalledWith("/refunds?order_id=o1", {
      amount: 100,
      reason: "other",
      reason_note: "item arrived cold",
      idempotency_key: "key-2",
    });
  });
});

describe("data service — notifications", () => {
  it("unwraps the authoritative unread count", async () => {
    apiMock.get.mockResolvedValue({ unread_count: 3 });

    expect(await getUnreadNotificationCount()).toBe(3);
    expect(apiMock.get).toHaveBeenCalledWith("/notifications/unread-count");
  });

  it("builds the inbox filter query and unwraps items", async () => {
    apiMock.get.mockResolvedValue({
      items: [{ id: "n1" }],
      total: 1,
      unread_count: 3,
    });

    const page = await getNotificationsPage({ unread_only: true, limit: 20 });
    expect(apiMock.get).toHaveBeenCalledWith(
      "/notifications?unread_only=true&limit=20",
    );
    expect(page.items).toHaveLength(1);
    expect(page.items[0]).toEqual({ id: "n1" });
  });

  it("patches the right endpoints for mark-read actions", async () => {
    apiMock.patch.mockResolvedValue({});

    await markNotificationRead("n1");
    expect(apiMock.patch).toHaveBeenCalledWith("/notifications/n1/read");

    await markAllNotificationsRead();
    expect(apiMock.patch).toHaveBeenCalledWith("/notifications/read-all");
  });
});
