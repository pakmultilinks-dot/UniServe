/**
 * Phase 60 (Workstream B) — Login screen behaviour tests.
 *
 * Asserts the observable states of the login form: empty-field validation,
 * trimmed-credential submission, server-error surfacing, and the
 * session-expired notice (P3-6).
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react-native";

const mockLogin = jest.fn();
const mockPinLogin = jest.fn();
let mockSessionExpired = false;

jest.mock("../contexts/AuthContext", () => ({
  useAuth: () => ({
    user: null,
    isAuthenticated: false,
    isLoading: false,
    isEmailVerified: false,
    sessionExpired: mockSessionExpired,
    login: (...args: unknown[]) => mockLogin(...args),
    pinLogin: (...args: unknown[]) => mockPinLogin(...args),
    logout: jest.fn(),
  }),
}));

jest.mock("../contexts/ThemeContext", () => ({
  useTheme: () => ({ resolvedTheme: "light" }),
}));

jest.mock("expo-router", () => ({
  useRouter: () => ({ push: jest.fn() }),
}));

jest.mock("../services/secure-storage", () => ({
  SecureStorage: {
    // No stored user — cold start stays on the password form.
    getItemAsync: jest.fn(async () => null),
    setItemAsync: jest.fn(async () => undefined),
    deleteItemAsync: jest.fn(async () => undefined),
  },
}));

import LoginScreen from "../../app/(auth)/login";

const fillForm = (email: string, password: string) => {
  fireEvent.changeText(
    screen.getByPlaceholderText("you@lgu.edu.pk"),
    email,
  );
  fireEvent.changeText(
    screen.getByPlaceholderText("Enter your password"),
    password,
  );
};

beforeEach(() => {
  mockLogin.mockReset();
  mockPinLogin.mockReset();
  mockSessionExpired = false;
});

describe("LoginScreen — form validation", () => {
  it("blocks submission and explains when both fields are empty", () => {
    render(<LoginScreen />);

    fireEvent.press(screen.getByText("Log In"));

    expect(
      screen.getByText("Please enter both email and password"),
    ).toBeTruthy();
    expect(mockLogin).not.toHaveBeenCalled();
  });
});

describe("LoginScreen — sign-in flow", () => {
  it("submits the trimmed email and the typed password", async () => {
    mockLogin.mockResolvedValue(undefined);
    render(<LoginScreen />);

    fillForm("  you@lgu.edu.pk  ", "Pass123!");
    fireEvent.press(screen.getByText("Log In"));

    await waitFor(() =>
      expect(mockLogin).toHaveBeenCalledWith(
        "you@lgu.edu.pk",
        "Pass123!",
      ),
    );
  });

  it("surfaces server errors and stays on the login form", async () => {
    mockLogin.mockRejectedValue(new Error("Invalid credentials"));
    render(<LoginScreen />);

    fillForm("you@lgu.edu.pk", "WrongPass!");
    fireEvent.press(screen.getByText("Log In"));

    expect(await screen.findByText("Invalid credentials")).toBeTruthy();
    // Still on the form — the login action remains available.
    expect(screen.getByText("Log In")).toBeTruthy();
  });
});

describe("LoginScreen — session expiry notice (P3-6)", () => {
  it("explains why the user was returned to the login screen", () => {
    mockSessionExpired = true;
    render(<LoginScreen />);

    expect(
      screen.getByText("Your session has expired. Please log in again."),
    ).toBeTruthy();
  });
});
