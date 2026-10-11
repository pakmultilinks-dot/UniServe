/**
 * Phase 60 (Workstream B) — WebDashboardGate behaviour tests (role gate).
 *
 * Staff/admin roles land on the mobile gate instead of ordering UI: the
 * screen must explain where the dashboard lives, identify the signed-in
 * role, and only sign out after explicit confirmation (no silent session
 * destruction).
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react-native";
import type { User } from "@uniserve/shared-types";

const mockLogout = jest.fn();
let mockGateUser: Partial<User> | null = null;

jest.mock("../contexts/AuthContext", () => ({
  useAuth: () => ({
    user: mockGateUser,
    isAuthenticated: mockGateUser !== null,
    isLoading: false,
    logout: (...args: unknown[]) => mockLogout(...args),
  }),
}));

jest.mock("../contexts/ThemeContext", () => ({
  useTheme: () => ({ resolvedTheme: "light" }),
}));

import WebDashboardGate from "../components/WebDashboardGate";

const MANAGER: User = {
  id: "m1",
  first_name: "Ayesha",
  last_name: "Khan",
  university_id: "LGU-2024-100",
  university_email: "ayesha.khan@lgu.edu.pk",
  category: "faculty",
  role: "cafeteria_manager",
  status: "active",
  email_verified: true,
  created_at: "2025-01-01T00:00:00Z",
};

beforeEach(() => {
  mockLogout.mockReset();
  mockGateUser = null;
});

describe("WebDashboardGate — role gate messaging", () => {
  it("explains that operational dashboards live on the web console", () => {
    mockGateUser = MANAGER;
    render(<WebDashboardGate />);

    expect(screen.getByText("Use the Web Dashboard")).toBeTruthy();
    expect(
      screen.getByText(/Sign in on a computer to manage orders/),
    ).toBeTruthy();
  });

  it("identifies the signed-in role in plain language", () => {
    mockGateUser = MANAGER;
    render(<WebDashboardGate />);

    expect(
      screen.getByText("Signed in as Ayesha Khan (Cafeteria Manager)"),
    ).toBeTruthy();
  });
});

describe("WebDashboardGate — sign-out confirmation", () => {
  it("does not sign out until the confirmation dialog is accepted", async () => {
    mockGateUser = MANAGER;
    render(<WebDashboardGate />);

    // First "Sign Out" tap only opens the confirmation dialog.
    fireEvent.press(screen.getAllByText("Sign Out")[0]);
    expect(
      await screen.findByText("Are you sure you want to sign out?"),
    ).toBeTruthy();
    expect(mockLogout).not.toHaveBeenCalled();

    // The dialog's confirm action carries the accessibility label.
    fireEvent.press(screen.getByLabelText("Sign Out"));

    await waitFor(() => expect(mockLogout).toHaveBeenCalledTimes(1));
  });

  it("keeps the session when the confirmation is cancelled", async () => {
    mockGateUser = MANAGER;
    render(<WebDashboardGate />);

    fireEvent.press(screen.getAllByText("Sign Out")[0]);
    await screen.findByText("Are you sure you want to sign out?");
    fireEvent.press(screen.getByText("Cancel"));

    expect(mockLogout).not.toHaveBeenCalled();
  });
});
