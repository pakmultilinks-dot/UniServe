import { beforeEach, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { render, screen, within } from "@testing-library/react";
const state = vi.hoisted(() => ({ user: { id: "u1", role: "university_admin", first_name: "Test", last_name: "User", university_email: "test@lgu.edu.pk" } }));
vi.mock("@/contexts/AuthContext", () => ({ useAuth: () => ({ user: state.user, isAuthenticated: true, isLoading: false }) }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/lib/api", async (original) => ({ ...(await original<typeof import("@/lib/api")>()), getCafeterias: vi.fn(), getMyCafeterias: vi.fn(), getNotifications: vi.fn(), getOrders: vi.fn(), getCafeteriaOrders: vi.fn() }));
vi.mock("next/link", () => ({ default: ({ children, href }: { children: ReactNode; href: string }) => <a href={href}>{children}</a> }));
import Dashboard from "@/app/dashboard/page";
import * as api from "@/lib/api";
const mock = vi.mocked(api);
beforeEach(() => {
  vi.clearAllMocks();
  mock.getCafeterias.mockResolvedValue([{ id: "c1", name: "Cafe", type: "student", operational_status: "open" }] as never);
  mock.getMyCafeterias.mockResolvedValue(["c1"]);
  mock.getNotifications.mockResolvedValue({ items: [], unread_count: 0, total: 0 });
  const orders = Array.from({ length: 6 }, (_, i) => ({ id: String(i), order_number: 100-i, status: i === 5 ? "pending" : "completed", created_at: `2026-10-${26-i}T08:00:00Z`, order_date: "2026-10-26", items: [], total_amount: 22000, currency: "PKR", cafeteria_id: "c1" }));
  mock.getCafeteriaOrders.mockResolvedValue({ orders, total: 6 } as never);
  mock.getOrders.mockResolvedValue(orders as never);
});
it.each(["university_admin", "cafeteria_staff", "student"])("counts an older active order beyond the five recent rows for %s", async (role) => {
  state.user.role = role;
  render(<Dashboard />);
  await screen.findByText("Order #100");
  const card = screen.getByText("Active Orders").parentElement!;
  expect(within(card).getByText("1")).toBeTruthy();
  expect(screen.queryByText("Order #95")).toBeNull();
});
