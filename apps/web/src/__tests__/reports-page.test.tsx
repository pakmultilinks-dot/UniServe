/**
 * Phase 60 (Workstream A) — Reports console page state tests.
 *
 * Asserts the observable states: genuinely-empty period, scoped-403 access
 * notice, generic report failure, and cafeteria-selector failure — errors
 * must never masquerade as "no data".
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ApiClientError } from "@uniserve/shared-types";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    getCafeterias: vi.fn(),
    getMyCafeterias: vi.fn(),
    getSalesReport: vi.fn(),
    getOrderSummaryReport: vi.fn(),
    getDailySalesReport: vi.fn(),
    getOrderVolumeReport: vi.fn(),
    getCancellationRateReport: vi.fn(),
    getSalesByCafeteriaReport: vi.fn(),
    getCafeteriaPerformanceReport: vi.fn(),
    getPopularItemsReport: vi.fn(),
    getInventoryStockLevelsReport: vi.fn(),
    getInventoryLowStockReport: vi.fn(),
    getInventoryTurnoverReport: vi.fn(),
    getCafeteriaPeakHoursReport: vi.fn(),
  };
});

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/dashboard/admin/reports",
}));

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({
    user: {
      id: "a1",
      role: "university_admin",
      first_name: "Admin",
      last_name: "One",
      university_email: "admin.one@lgu.edu.pk",
    },
    logout: vi.fn().mockResolvedValue(undefined),
  }),
}));

import * as api from "@/lib/api";
import ReportsPage from "@/app/dashboard/admin/reports/page";

const apiMock = vi.mocked(api);

/** Zeroed backend report payloads — valid shapes, no orders in the period. */
function mockZeroedReports() {
  apiMock.getCafeterias.mockResolvedValue([
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
  ]);
  apiMock.getSalesReport.mockResolvedValue({
    total_orders: 0,
    total_revenue: 0,
    net_revenue: 0,
    total_refunded: 0,
    online_payment_volume: 0,
    cash_payment_volume: 0,
  });
  apiMock.getOrderSummaryReport.mockResolvedValue({
    total_orders: 0,
    status_breakdown: {
      pending: 0,
      preparing: 0,
      ready: 0,
      completed: 0,
      cancelled: 0,
    },
    type_breakdown: { immediate: 0, scheduled: 0 },
    payment_breakdown: { cash: 0, online: 0 },
    cancellation_rate: 0,
    completion_rate: 0,
  });
  apiMock.getDailySalesReport.mockResolvedValue({ rows: [], currency: "PKR" });
  // The page's trend/table memos read report.volume.daily (and the full
  // render branch reads report.volume.hourly) — both must be arrays.
  apiMock.getOrderVolumeReport.mockResolvedValue({ daily: [], hourly: [] });
  apiMock.getCancellationRateReport.mockResolvedValue({
    total_orders: 0,
    cancelled_orders: 0,
    cancellation_rate: 0,
    cancellation_reasons: {},
  });
  apiMock.getSalesByCafeteriaReport.mockResolvedValue({
    rows: [],
    currency: "PKR",
  });
  apiMock.getPopularItemsReport.mockResolvedValue({
    cafeteria_id: "c1",
    items: [],
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  window.sessionStorage.clear();
  mockZeroedReports();
});

describe("ReportsPage — page states", () => {
  it("shows the genuinely-empty period state for zeroed report data", async () => {
    render(<ReportsPage />);

    expect(
      await screen.findByText("No orders found for this period"),
    ).toBeInTheDocument();
    expect(screen.getByText("Reports & Analytics")).toBeInTheDocument();
  });

  it("shows an explicit access notice on a scoped 403, not an empty report", async () => {
    apiMock.getSalesReport.mockRejectedValue(
      new ApiClientError(403, "Manager reports are cafeteria-scoped"),
    );

    render(<ReportsPage />);

    expect(
      await screen.findByText(
        "You don't have access to this cafeteria's reports",
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("No orders found for this period"),
    ).not.toBeInTheDocument();
  });

  it("shows a retryable error state on generic report failure", async () => {
    apiMock.getSalesReport.mockRejectedValue(
      new Error("report service down"),
    );

    render(<ReportsPage />);

    expect(
      await screen.findByText(/report service down|something went wrong/i),
    ).toBeInTheDocument();
    expect(screen.getByText("Try again")).toBeInTheDocument();
    expect(
      screen.queryByText("No orders found for this period"),
    ).not.toBeInTheDocument();
  });

  it("surfaces cafeteria selector failure instead of an empty selector", async () => {
    apiMock.getCafeterias.mockRejectedValue(new Error("cafeterias down"));

    render(<ReportsPage />);

    expect(
      await screen.findByText(/cafeterias down|something went wrong/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("No orders found for this period"),
    ).not.toBeInTheDocument();
  });
});


it("identifies report loading instead of showing unexplained blank cards", async () => {
  apiMock.getSalesReport.mockReturnValue(new Promise(() => {}));
  render(<ReportsPage />);
  expect(await screen.findByRole("status")).toHaveTextContent("Loading reports");
});
