/**
 * Phase 60 (Workstream A) — Refunds console page state tests.
 *
 * Asserts the observable states: empty result, populated table rows, and
 * explicit load-failure state (never masquerading as "No refunds").
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    getAllRefunds: vi.fn(),
    getAdminRefund: vi.fn(),
    processRefund: vi.fn(),
    rejectRefund: vi.fn(),
  };
});

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/dashboard/admin/refunds",
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
import RefundsPage from "@/app/dashboard/admin/refunds/page";
import { ToastProvider } from "@/components/ui/Toast";
import type { RefundAdminResponse } from "@uniserve/shared-types";

const apiMock = vi.mocked(api);

function makeRefund(
  overrides: Partial<RefundAdminResponse> = {},
): RefundAdminResponse {
  return {
    id: "r1",
    order_id: "o1",
    payment_id: "p1",
    user_id: "s1",
    amount: 250,
    currency: "PKR",
    status: "pending",
    reason: "item_unavailable",
    requested_by: "s1",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    student: {
      id: "s1",
      first_name: "Sana",
      last_name: "Ali",
      university_email: "sana.ali@lgu.edu.pk",
      university_id: "LGU-2024-042",
      role: "student",
    },
    order: {
      id: "o1",
      order_number: 42,
      status: "delivered",
      payment_method: "cash_on_delivery",
      total_amount: 250,
      currency: "PKR",
      created_at: new Date().toISOString(),
    },
    payment: {
      id: "p1",
      status: "succeeded",
      amount: 250,
      currency: "PKR",
    },
    ...overrides,
  };
}

function renderPage() {
  return render(
    <ToastProvider>
      <RefundsPage />
    </ToastProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("RefundsPage — page states", () => {
  it("shows the genuinely-empty refunds state", async () => {
    apiMock.getAllRefunds.mockResolvedValue({ refunds: [], total: 0 });

    renderPage();

    expect(await screen.findByText("No refunds")).toBeInTheDocument();
    expect(screen.getByText("Refund requests will appear here.")).toBeInTheDocument();
  });

  it("renders refund rows with order, student, and status", async () => {
    apiMock.getAllRefunds.mockResolvedValue({
      refunds: [makeRefund()],
      total: 1,
    });

    renderPage();

    expect(await screen.findByText("#42")).toBeInTheDocument();
    expect(screen.getByText("Sana Ali")).toBeInTheDocument();
    expect(screen.getByText("sana.ali@lgu.edu.pk")).toBeInTheDocument();
    expect(screen.getAllByText("pending").length).toBeGreaterThan(0);
    expect(screen.getAllByText("View").length).toBeGreaterThan(0);
  });

  it("surfaces load failures instead of masquerading as no refunds", async () => {
    apiMock.getAllRefunds.mockRejectedValue(new Error("refund backend down"));

    renderPage();

    expect(
      await screen.findByText(/refund backend down|something went wrong/i),
    ).toBeInTheDocument();
    expect(screen.queryByText("No refunds")).not.toBeInTheDocument();
  });
});
