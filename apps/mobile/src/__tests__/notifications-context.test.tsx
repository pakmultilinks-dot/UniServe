/**
 * Phase 60 (Workstream B) — NotificationsContext behaviour tests.
 *
 * The badge is a passive indicator fed by the authoritative server count:
 * fetch only while authenticated, swallow failures, re-fetch on demand.
 */

import React from "react";
import { View, Text, Pressable } from "react-native";
import { render, screen, fireEvent, waitFor } from "@testing-library/react-native";

let mockIsAuthenticated = false;

jest.mock("../contexts/AuthContext", () => ({
  useAuth: () => ({ isAuthenticated: mockIsAuthenticated }),
}));

jest.mock("../services/data", () => ({
  getUnreadNotificationCount: jest.fn(),
}));

import { getUnreadNotificationCount } from "../services/data";
import {
  NotificationsProvider,
  useNotifications,
} from "../contexts/NotificationsContext";

const unreadMock = getUnreadNotificationCount as jest.MockedFunction<
  typeof getUnreadNotificationCount
>;

function BadgeHarness() {
  const { unreadCount, refreshUnreadCount } = useNotifications();
  return (
    <View>
      <Text testID="unread">{String(unreadCount)}</Text>
      <Pressable
        testID="refresh"
        onPress={() => {
          refreshUnreadCount().catch(() => undefined);
        }}
      >
        <Text>refresh</Text>
      </Pressable>
    </View>
  );
}

const renderBadge = () =>
  render(
    <NotificationsProvider>
      <BadgeHarness />
    </NotificationsProvider>,
  );

beforeEach(() => {
  jest.clearAllMocks();
  mockIsAuthenticated = false;
});

describe("NotificationsProvider — badge count", () => {
  it("fetches the authoritative unread count when authenticated", async () => {
    mockIsAuthenticated = true;
    unreadMock.mockResolvedValue(3);

    renderBadge();

    await waitFor(() =>
      expect(screen.getByTestId("unread").props.children).toBe("3"),
    );
    expect(unreadMock).toHaveBeenCalledTimes(1);
  });

  it("never calls the API while logged out", () => {
    mockIsAuthenticated = false;

    renderBadge();

    expect(unreadMock).not.toHaveBeenCalled();
    expect(screen.getByTestId("unread").props.children).toBe("0");
  });

  it("swallows fetch failures — the badge stays passive", async () => {
    mockIsAuthenticated = true;
    unreadMock.mockRejectedValue(new Error("badge backend down"));

    renderBadge();

    await waitFor(() => expect(unreadMock).toHaveBeenCalled());
    // No crash, no stale value — the count simply stays at zero.
    expect(screen.getByTestId("unread").props.children).toBe("0");
  });

  it("re-queries the server on explicit refresh", async () => {
    mockIsAuthenticated = true;
    unreadMock.mockResolvedValueOnce(2).mockResolvedValueOnce(5);

    renderBadge();
    await waitFor(() =>
      expect(screen.getByTestId("unread").props.children).toBe("2"),
    );

    fireEvent.press(screen.getByTestId("refresh"));

    await waitFor(() =>
      expect(screen.getByTestId("unread").props.children).toBe("5"),
    );
    expect(unreadMock).toHaveBeenCalledTimes(2);
  });
});
