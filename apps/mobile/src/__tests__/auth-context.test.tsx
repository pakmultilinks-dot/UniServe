/**
 * Phase 60 (Workstream B) — Mobile AuthContext behaviour tests.
 *
 * Asserts the provider's observable behaviour: cold-start state, password
 * login persistence, PIN login, logout (local clear even on server
 * failure), and the session-expiry hook used by the login screen.
 */

import React from "react";
import { View, Text, Pressable } from "react-native";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react-native";
import type { TokenPair, User } from "@uniserve/shared-types";

jest.mock("../services/auth", () => ({
  login: jest.fn(),
  pinLogin: jest.fn(),
  logout: jest.fn(),
  logoutAll: jest.fn(),
  register: jest.fn(),
  getCurrentUser: jest.fn(),
  refreshTokens: jest.fn(),
}));

jest.mock("../services/secure-storage", () => ({
  SecureStorage: {
    getItemAsync: jest.fn(),
    setItemAsync: jest.fn(),
    deleteItemAsync: jest.fn(),
  },
}));

jest.mock("../services/api", () => ({
  loadPersistedTokens: jest.fn().mockResolvedValue(undefined),
  secureStoreTokenProvider: {
    getAccessToken: jest.fn(() => null),
    getRefreshToken: jest.fn(() => null),
    setTokens: jest.fn(),
    clearTokens: jest.fn(),
  },
  setOnAuthFailure: jest.fn(),
}));

import * as authApi from "../services/auth";
import { SecureStorage } from "../services/secure-storage";
import { secureStoreTokenProvider, setOnAuthFailure } from "../services/api";
import { AuthProvider, useAuth } from "../contexts/AuthContext";

const authApiMock = authApi as jest.Mocked<typeof authApi>;
const storageMock = SecureStorage as jest.Mocked<typeof SecureStorage>;
const providerMock = secureStoreTokenProvider as jest.Mocked<
  typeof secureStoreTokenProvider
>;
const onAuthFailureMock = setOnAuthFailure as jest.MockedFunction<
  typeof setOnAuthFailure
>;

const USER: User = {
  id: "u1",
  first_name: "Ayesha",
  last_name: "Khan",
  university_id: "LGU-2024-001",
  university_email: "ayesha.khan@lgu.edu.pk",
  category: "student",
  role: "student",
  status: "active",
  email_verified: true,
  created_at: "2025-01-01T00:00:00Z",
};

const TOKENS: TokenPair = {
  access_token: "access-1",
  refresh_token: "refresh-1",
  token_type: "bearer",
  expires_in: 1800,
};

function AuthHarness() {
  const auth = useAuth();
  return (
    <View>
      <Text testID="loading">{String(auth.isLoading)}</Text>
      <Text testID="authenticated">{String(auth.isAuthenticated)}</Text>
      <Text testID="email">{auth.user?.university_email ?? "none"}</Text>
      <Text testID="expired">{String(auth.sessionExpired)}</Text>
      <Pressable
        testID="login-btn"
        onPress={() => {
          auth.login("s@lgu.edu.pk", "Pass123!").catch(() => undefined);
        }}
      >
        <Text>login</Text>
      </Pressable>
      <Pressable
        testID="pin-btn"
        onPress={() => {
          auth.pinLogin("u1", "1234").catch(() => undefined);
        }}
      >
        <Text>pin</Text>
      </Pressable>
      <Pressable
        testID="logout-btn"
        onPress={() => {
          auth.logout().catch(() => undefined);
        }}
      >
        <Text>logout</Text>
      </Pressable>
    </View>
  );
}

const renderAuth = () =>
  render(
    <AuthProvider>
      <AuthHarness />
    </AuthProvider>,
  );

beforeEach(() => {
  jest.clearAllMocks();
  storageMock.getItemAsync.mockResolvedValue(null);
  storageMock.setItemAsync.mockResolvedValue(undefined);
  storageMock.deleteItemAsync.mockResolvedValue(undefined);
  providerMock.getAccessToken.mockReturnValue(null);
});

describe("mobile AuthProvider — cold start", () => {
  it("finishes loading with no session when nothing is persisted", async () => {
    renderAuth();

    await waitFor(() =>
      expect(screen.getByTestId("loading").props.children).toBe("false"),
    );
    expect(screen.getByTestId("authenticated").props.children).toBe("false");
    expect(screen.getByTestId("email").props.children).toBe("none");
  });
});

describe("mobile AuthProvider — password login", () => {
  it("persists tokens and the user, then authenticates", async () => {
    authApiMock.login.mockResolvedValue({ user: USER, tokens: TOKENS });
    renderAuth();
    await waitFor(() =>
      expect(screen.getByTestId("loading").props.children).toBe("false"),
    );

    fireEvent.press(screen.getByTestId("login-btn"));

    await waitFor(() =>
      expect(screen.getByTestId("authenticated").props.children).toBe("true"),
    );
    expect(authApiMock.login).toHaveBeenCalledWith({
      university_email: "s@lgu.edu.pk",
      password: "Pass123!",
    });
    expect(providerMock.setTokens).toHaveBeenCalledWith(
      TOKENS.access_token,
      TOKENS.refresh_token,
    );
    expect(storageMock.setItemAsync).toHaveBeenCalledWith(
      "uniserve_user",
      JSON.stringify(USER),
    );
    expect(screen.getByTestId("email").props.children).toBe(
      USER.university_email,
    );
    expect(screen.getByTestId("expired").props.children).toBe("false");
  });

  it("keeps the user signed out when the login call fails", async () => {
    authApiMock.login.mockRejectedValue(new Error("Invalid credentials"));
    renderAuth();
    await waitFor(() =>
      expect(screen.getByTestId("loading").props.children).toBe("false"),
    );

    fireEvent.press(screen.getByTestId("login-btn"));

    // The rejection is handled (no crash) and the state stays signed out.
    await waitFor(() => expect(authApiMock.login).toHaveBeenCalled());
    expect(screen.getByTestId("authenticated").props.children).toBe("false");
    expect(screen.getByTestId("email").props.children).toBe("none");
  });
});

describe("mobile AuthProvider — PIN login", () => {
  it("persists the session exactly like password login", async () => {
    authApiMock.pinLogin.mockResolvedValue({ user: USER, tokens: TOKENS });
    renderAuth();
    await waitFor(() =>
      expect(screen.getByTestId("loading").props.children).toBe("false"),
    );

    fireEvent.press(screen.getByTestId("pin-btn"));

    await waitFor(() =>
      expect(screen.getByTestId("authenticated").props.children).toBe("true"),
    );
    expect(authApiMock.pinLogin).toHaveBeenCalledWith({
      user_id: "u1",
      pin: "1234",
    });
    expect(providerMock.setTokens).toHaveBeenCalledWith(
      TOKENS.access_token,
      TOKENS.refresh_token,
    );
    expect(storageMock.setItemAsync).toHaveBeenCalledWith(
      "uniserve_user",
      JSON.stringify(USER),
    );
  });
});

describe("mobile AuthProvider — logout", () => {
  it("clears the local session even when the server call fails", async () => {
    authApiMock.login.mockResolvedValue({ user: USER, tokens: TOKENS });
    authApiMock.logout.mockRejectedValue(new Error("server unreachable"));
    renderAuth();
    await waitFor(() =>
      expect(screen.getByTestId("loading").props.children).toBe("false"),
    );
    fireEvent.press(screen.getByTestId("login-btn"));
    await waitFor(() =>
      expect(screen.getByTestId("authenticated").props.children).toBe("true"),
    );

    fireEvent.press(screen.getByTestId("logout-btn"));

    await waitFor(() =>
      expect(screen.getByTestId("authenticated").props.children).toBe("false"),
    );
    expect(authApiMock.logout).toHaveBeenCalled();
    expect(providerMock.clearTokens).toHaveBeenCalled();
    expect(storageMock.deleteItemAsync).toHaveBeenCalledWith("uniserve_user");
  });
});

describe("mobile AuthProvider — session expiry hook", () => {
  it("clears user state and flags expiry when onAuthFailure fires", async () => {
    authApiMock.login.mockResolvedValue({ user: USER, tokens: TOKENS });
    renderAuth();
    await waitFor(() =>
      expect(screen.getByTestId("loading").props.children).toBe("false"),
    );
    fireEvent.press(screen.getByTestId("login-btn"));
    await waitFor(() =>
      expect(screen.getByTestId("authenticated").props.children).toBe("true"),
    );

    const failureHook = onAuthFailureMock.mock.calls[0]?.[0];
    expect(typeof failureHook).toBe("function");
    act(() => {
      failureHook!();
    });

    expect(screen.getByTestId("authenticated").props.children).toBe("false");
    expect(screen.getByTestId("email").props.children).toBe("none");
    expect(screen.getByTestId("expired").props.children).toBe("true");
  });
});
