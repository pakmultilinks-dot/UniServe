/**
 * Phase 60 (Workstream A) — Notifications page state tests.
 *
 * Asserts the observable page states: empty inbox, populated list with
 * unread count, explicit load-failure state (never masquerading as "No
 * notifications"), and mark-read behaviour.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    getNotifications: vi.fn(),
    markNotificationRead: vi.fn(),
    markAllNotificationsRead: vi.fn(),
  };
});

import * as api from "@/lib/api";
import NotificationsPage from "@/app/dashboard/notifications/page";
import { ToastProvider } from "@/components/ui/Toast";
import type { Notification } from "@uniserve/shared-types";

const apiMock = vi.mocked(api);

function makeNotification(overrides: Partial<Notification> = {}): Notification {
  return {
    id: "n1",
    notification_type: "order_created",
    title: "Order #1042 placed",
    body: "Your order has been received.",
    is_read: false,
    delivery_status: "delivered",
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

function renderPage() {
  return render(
    <ToastProvider>
      <NotificationsPage />
    </ToastProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("NotificationsPage — page states", () => {
  it("shows the genuinely-empty inbox state", async () => {
    apiMock.getNotifications.mockResolvedValue({
      items: [],
      total: 0,
      unread_count: 0,
    });

    renderPage();

    expect(await screen.findByText("No notifications")).toBeInTheDocument();
    expect(screen.getByText("You're all caught up!")).toBeInTheDocument();
  });

  it("renders the list with unread count and notification content", async () => {
    apiMock.getNotifications.mockResolvedValue({
      items: [makeNotification()],
      total: 1,
      unread_count: 1,
    });

    renderPage();

    expect(
      await screen.findByText("1 unread notification"),
    ).toBeInTheDocument();
    expect(screen.getByText("Order #1042 placed")).toBeInTheDocument();
    expect(screen.getByText("Mark All Read")).toBeInTheDocument();
  });

  it("surfaces load failures instead of masquerading as an empty inbox", async () => {
    apiMock.getNotifications.mockRejectedValue(new Error("backend exploded"));

    renderPage();

    expect(
      await screen.findByText(/backend exploded|something went wrong/i),
    ).toBeInTheDocument();
    expect(screen.queryByText("No notifications")).not.toBeInTheDocument();
    expect(screen.queryByText("You're all caught up!")).not.toBeInTheDocument();
  });
});

describe("NotificationsPage — mark-read behaviour", () => {
  it("marks a notification read and decrements the unread count", async () => {
    apiMock.getNotifications.mockResolvedValue({
      items: [makeNotification()],
      total: 1,
      unread_count: 1,
    });
    apiMock.markNotificationRead.mockResolvedValue({});

    renderPage();

    fireEvent.click(await screen.findByText("Order #1042 placed"));

    await waitFor(() =>
      expect(apiMock.markNotificationRead).toHaveBeenCalledWith("n1"),
    );
    await waitFor(() =>
      // The page renders "N unread notification(s)" — plural for 0.
      expect(screen.getByText("0 unread notifications")).toBeInTheDocument(),
    );
    // Mark All Read disappears once nothing is unread.
    await waitFor(() =>
      expect(screen.queryByText("Mark All Read")).not.toBeInTheDocument(),
    );
  });

  it("surfaces mark-read failures via toast instead of silently no-oping", async () => {
    apiMock.getNotifications.mockResolvedValue({
      items: [makeNotification()],
      total: 1,
      unread_count: 1,
    });
    apiMock.markNotificationRead.mockRejectedValue(new Error("write denied"));

    renderPage();

    fireEvent.click(await screen.findByText("Order #1042 placed"));

    // getApiErrorInfo maps unknown errors to its generic user-facing message.
    expect(
      await screen.findByText(/something went wrong/i),
    ).toBeInTheDocument();
    // Unread state must be unchanged after the failed action.
    expect(screen.getByText("1 unread notification")).toBeInTheDocument();
  });
});
