/**
 * Phase 60 (Workstream A) — Orders console page state tests.
 *
 * Asserts the observable queue states: empty queue, scoped-403 access
 * notice, and generic load failure (never masquerading as an empty queue).
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { ApiClientError } from "@uniserve/shared-types";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    getCafeterias: vi.fn(),
    getMyCafeterias: vi.fn(),
    getCafeteriaOrders: vi.fn(),
    getOrderDetail: vi.fn(),
    getOrderEta: vi.fn(),
    collectOrder: vi.fn(),
  };
});

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/dashboard/orders",
}));

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({
    user: {
      id: "m1",
      role: "cafeteria_manager",
      first_name: "Manager",
      last_name: "One",
      university_email: "manager.one@lgu.edu.pk",
    },
    logout: vi.fn().mockResolvedValue(undefined),
  }),
}));

import * as api from "@/lib/api";
import OrdersPage from "@/app/dashboard/orders/page";
import { ToastProvider } from "@/components/ui/Toast";
import type { Cafeteria, Order } from "@uniserve/shared-types";

const apiMock = vi.mocked(api);

const CAFETERIAS: Cafeteria[] = [
  {
    id: "c1",
    name: "Main Cafeteria",
    type: "student",
    timezone: "Asia/Karachi",
    operational_status: "open",
    is_active: true,
    created_at: "2025-01-01T00:00:00Z",
    updated_at: "2025-01-01T00:00:00Z",
  },
];

function renderPage() {
  return render(
    <ToastProvider>
      <OrdersPage />
    </ToastProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  window.sessionStorage.clear();
  window.history.replaceState({}, "", "/dashboard/orders");
  apiMock.getCafeterias.mockResolvedValue(CAFETERIAS);
  apiMock.getMyCafeterias.mockResolvedValue(["c1"]);
});

describe("OrdersPage — recent-order deep links", () => {
  it("selects the linked cafeteria and clears stale filters from a prior visit", async () => {
    apiMock.getCafeterias.mockResolvedValue([
      ...CAFETERIAS,
      { ...CAFETERIAS[0], id: "c2", name: "Student Cafeteria" },
    ]);
    apiMock.getMyCafeterias.mockResolvedValue(["c1", "c2"]);
    apiMock.getCafeteriaOrders.mockResolvedValue({ orders: [], total: 0 });
    window.sessionStorage.setItem("orders-console-filters", JSON.stringify({
      cafeteria: "c1",
      tab: "pending",
      date: "2026-10-19",
    }));
    window.history.replaceState({}, "", "/dashboard/orders?cafeteria=c2");

    renderPage();

    expect(await screen.findByText("No orders yet")).toBeInTheDocument();
    expect(screen.getByRole("combobox")).toHaveValue("c2");
    expect(apiMock.getCafeteriaOrders).toHaveBeenCalledWith(
      "c2",
      expect.objectContaining({ status: undefined, order_date: undefined }),
    );
    expect(screen.queryByText(/Date filter:/)).not.toBeInTheDocument();
  });
});

describe("OrdersPage — queue states", () => {
  it("shows the empty queue state when no orders match the filter", async () => {
    apiMock.getCafeteriaOrders.mockResolvedValue({ orders: [], total: 0 });

    renderPage();

    // Default tab is "all" (orders auto-advance out of "pending" within
    // seconds, so a pending default hid freshly placed mobile orders).
    expect(await screen.findByText("No orders yet")).toBeInTheDocument();
    expect(apiMock.getCafeteriaOrders).toHaveBeenCalledWith(
      "c1",
      expect.objectContaining({ status: undefined }),
    );
  });

  it("shows an explicit access notice on a scoped 403, not an empty queue", async () => {
    apiMock.getCafeteriaOrders.mockRejectedValue(
      new ApiClientError(403, "Not assigned to this cafeteria"),
    );

    renderPage();

    expect(
      await screen.findByText(
        "You don't have access to this cafeteria's orders",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Not assigned to this cafeteria")).toBeInTheDocument();
    expect(screen.queryByText("No pending orders")).not.toBeInTheDocument();
  });

  it("shows a retryable error state on generic load failure", async () => {
    apiMock.getCafeteriaOrders.mockRejectedValue(new Error("queue down"));

    renderPage();

    expect(
      await screen.findByText(/queue down|something went wrong/i),
    ).toBeInTheDocument();
    expect(screen.queryByText("No pending orders")).not.toBeInTheDocument();
  });

  it("surfaces cafeteria selector failure instead of an empty selector", async () => {
    apiMock.getCafeterias.mockRejectedValue(new Error("selector down"));

    renderPage();

    expect(
      await screen.findByText(/selector down|something went wrong/i),
    ).toBeInTheDocument();
    expect(screen.queryByText("No pending orders")).not.toBeInTheDocument();
  });
});

// ─── F-ACC-06 — Prepare action gating ───────────────────────────────
// The staff/manager queue must not offer "Prepare" on a pending order
// until it has been confirmed (`confirmed_at` set) — mirroring the
// server's workflow rule (prepare on an unconfirmed order → HTTP 400).
// Note: status tabs and StatusBadge render raw lowercase status text
// (capitalization is CSS-only), so these capitalized button-label
// assertions are unambiguous.

function makeOrder(
  overrides: Partial<Order> & { order_number: number },
): Order {
  return {
    id: `order-${overrides.order_number}`,
    collection_token: `TOK-${overrides.order_number}`,
    user_id: "u1",
    cafeteria_id: "c1",
    status: "pending",
    order_type: "immediate",
    payment_method: "cash",
    total_amount: 45000,
    currency: "PKR",
    order_date: "2026-10-08",
    items: [
      {
        id: `item-${overrides.order_number}`,
        item_name: "Chicken Biryani",
        unit_price: 45000,
        quantity: 1,
        subtotal: 45000,
        currency: "PKR",
      },
    ],
    inventory_reserved: false,
    created_at: "2026-10-08T12:00:00Z",
    updated_at: "2026-10-08T12:00:00Z",
    ...overrides,
  };
}

describe("OrdersPage — quiet background polling", () => {
  it("keeps the visible queue in place while a background refresh is pending", async () => {
    apiMock.getCafeteriaOrders.mockResolvedValue({
      orders: [makeOrder({ order_number: 905, status: "pending" })],
      total: 1,
    });
    // JSDOM may start with document.hidden true in a headless CI runner.
    // Make this an explicitly visible-tab test so the polling path runs.
    const hiddenDescriptor = Object.getOwnPropertyDescriptor(document, "hidden");
    Object.defineProperty(document, "hidden", { configurable: true, value: false });
    const intervalSpy = vi.spyOn(globalThis, "setInterval");

    try {
      renderPage();
      expect(await screen.findByText("Confirm")).toBeInTheDocument();

      // The next poll is deliberately slow. Existing queue items should stay
      // visible; a background refresh must not replace them with skeletons.
      apiMock.getCafeteriaOrders.mockImplementationOnce(
        () => new Promise(() => {}),
      );
      // Initial render registers a callback with an empty cafeteria before
      // the selector resolves. Use the latest callback after the cafeteria loads.
      const poll = intervalSpy.mock.calls.filter(([, delay]) => delay === 5000).at(-1)?.[0];
      expect(poll).toBeTypeOf("function");

      const requestsBeforePoll = apiMock.getCafeteriaOrders.mock.calls.length;
      await act(async () => {
        (poll as () => void)();
      });

      expect(apiMock.getCafeteriaOrders).toHaveBeenCalledTimes(requestsBeforePoll + 1);
      expect(screen.getByText("Confirm")).toBeInTheDocument();
      expect(document.querySelector(".skeleton")).toBeNull();
    } finally {
      intervalSpy.mockRestore();
      apiMock.getCafeteriaOrders.mockReset();
      if (hiddenDescriptor) {
        Object.defineProperty(document, "hidden", hiddenDescriptor);
      } else {
        Reflect.deleteProperty(document, "hidden");
      }
    }
  });
});

describe("OrdersPage — Prepare action gating (F-ACC-06)", () => {
  it("Case 1 — pending, unconfirmed: Confirm is offered and Prepare is not", async () => {
    apiMock.getCafeteriaOrders.mockResolvedValue({
      orders: [makeOrder({ order_number: 901, status: "pending" })],
      total: 1,
    });

    renderPage();

    expect(await screen.findByText("Confirm")).toBeInTheDocument();
    expect(screen.queryByText("Prepare")).not.toBeInTheDocument();
  });

  it("Case 2 — pending, confirmed: Prepare is offered and Confirm is not", async () => {
    apiMock.getCafeteriaOrders.mockResolvedValue({
      orders: [
        makeOrder({
          order_number: 902,
          status: "pending",
          confirmed_at: "2026-10-08T12:05:00Z",
        }),
      ],
      total: 1,
    });

    renderPage();

    expect(await screen.findByText("Prepare")).toBeInTheDocument();
    expect(screen.queryByText("Confirm")).not.toBeInTheDocument();
  });

  it("Case 3 — preparing/ready workflow is unaffected (Ready and Collect still offered)", async () => {
    apiMock.getCafeteriaOrders.mockResolvedValue({
      orders: [
        makeOrder({
          order_number: 903,
          status: "preparing",
          confirmed_at: "2026-10-08T12:05:00Z",
          preparation_started_at: "2026-10-08T12:06:00Z",
        }),
        makeOrder({
          order_number: 904,
          status: "ready",
          confirmed_at: "2026-10-08T12:05:00Z",
          preparation_started_at: "2026-10-08T12:06:00Z",
          ready_at: "2026-10-08T12:10:00Z",
        }),
      ],
      total: 2,
    });

    renderPage();

    expect(await screen.findByText("Ready")).toBeInTheDocument();
    expect(screen.getByText("Collect")).toBeInTheDocument();
    expect(screen.queryByText("Prepare")).not.toBeInTheDocument();
    expect(screen.queryByText("Confirm")).not.toBeInTheDocument();
  });
});


describe("OrdersPage — open details after collection", () => {
  it("updates the dialog as well as the queue and removes stale Collect/Delay actions", async () => {
    let current = makeOrder({ order_number: 991, status: "ready", customer_name: "Demo Student" });
    apiMock.getCafeteriaOrders.mockImplementation(async () => ({ orders: [current], total: 1 }));
    apiMock.getOrderDetail.mockImplementation(async () => current);
    apiMock.getOrderEta.mockResolvedValue({ eta_minutes: 25 } as any);
    apiMock.collectOrder.mockImplementation(async () => {
      current = { ...current, status: "completed", collected_at: "2026-10-08T12:20:00Z", updated_at: "2026-10-08T12:20:00Z" };
      return current;
    });
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Details" }));
    const dialog = await screen.findByRole("dialog", { name: "Order #991" });
    expect(await within(dialog).findByText("Demo Student")).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: "Collect" }));
    fireEvent.click(await screen.findByRole("button", { name: "Confirm Collect" }));
    await waitFor(() => expect(within(dialog).getByText(/^completed$/i)).toBeInTheDocument());
    expect(within(dialog).queryByRole("button", { name: "Collect" })).not.toBeInTheDocument();
    expect(within(dialog).queryByRole("button", { name: "Delay" })).not.toBeInTheDocument();
    expect(within(dialog).queryByText(/Computed ETA/)).not.toBeInTheDocument();
    expect(apiMock.collectOrder).toHaveBeenCalledWith({ order_number: 991 });
  });
});
