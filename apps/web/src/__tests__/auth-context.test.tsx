/**
 * Phase 60 (Workstream A) — AuthContext behaviour tests.
 *
 * Asserts the provider's observable behaviour: silent refresh on mount,
 * login/logout state transitions, and role checks.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

vi.mock("@/lib/api", () => ({
  setOnAuthFailure: vi.fn(),
  getCurrentUser: vi.fn(),
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
}));

import * as authApi from "@/lib/api";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import type { TokenPair, User } from "@uniserve/shared-types";

const authApiMock = vi.mocked(authApi);

const USER: User = {
  id: "u1",
  first_name: "Ayesha",
  last_name: "Khan",
  university_id: "LGU-2024-001",
  university_email: "ayesha.khan@lgu.edu.pk",
  category: "student",
  role: "cafeteria_manager",
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

function Harness() {
  const { user, isAuthenticated, isLoading, hasRole } = useAuth();
  return (
    <div>
      <p data-testid="loading">{String(isLoading)}</p>
      <p data-testid="authenticated">{String(isAuthenticated)}</p>
      <p data-testid="email">{user?.university_email ?? "none"}</p>
      <p data-testid="is-manager">{String(hasRole("cafeteria_manager"))}</p>
      <p data-testid="is-admin">{String(hasRole(["university_admin"]))}</p>
    </div>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("AuthProvider — session restoration on mount", () => {
  it("loads the current user when a session already exists", async () => {
    authApiMock.getCurrentUser.mockResolvedValue(USER);

    render(
      <AuthProvider>
        <Harness />
      </AuthProvider>,
    );

    expect(screen.getByTestId("loading").textContent).toBe("true");
    await waitFor(() =>
      expect(screen.getByTestId("loading").textContent).toBe("false"),
    );
    expect(screen.getByTestId("authenticated").textContent).toBe("true");
    expect(screen.getByTestId("email").textContent).toBe(USER.university_email);
  });

  it("stays unauthenticated when silent refresh fails", async () => {
    authApiMock.getCurrentUser.mockRejectedValue(
      new Error("Session expired. Please log in again."),
    );

    render(
      <AuthProvider>
        <Harness />
      </AuthProvider>,
    );

    await waitFor(() =>
      expect(screen.getByTestId("loading").textContent).toBe("false"),
    );
    expect(screen.getByTestId("authenticated").textContent).toBe("false");
    expect(screen.getByTestId("email").textContent).toBe("none");
  });

  it("hasRole checks single roles and role arrays", async () => {
    authApiMock.getCurrentUser.mockResolvedValue(USER);

    render(
      <AuthProvider>
        <Harness />
      </AuthProvider>,
    );

    await waitFor(() =>
      expect(screen.getByTestId("authenticated").textContent).toBe("true"),
    );
    expect(screen.getByTestId("is-manager").textContent).toBe("true");
    expect(screen.getByTestId("is-admin").textContent).toBe("false");
  });
});

describe("AuthProvider — login and logout transitions", () => {
  it("login sets the authenticated user", async () => {
    authApiMock.getCurrentUser.mockRejectedValue(new Error("no session"));
    authApiMock.login.mockResolvedValue({ user: USER, tokens: TOKENS });

    const LoginHarness = () => {
      const { login, user, isAuthenticated } = useAuth();
      return (
        <div>
          <button
            onClick={async () => {
              await login("ayesha.khan@lgu.edu.pk", "StrongPass1!");
            }}
          >
            Sign in
          </button>
          <p data-testid="authenticated">{String(isAuthenticated)}</p>
          <p data-testid="email">{user?.university_email ?? "none"}</p>
        </div>
      );
    };

    render(
      <AuthProvider>
        <LoginHarness />
      </AuthProvider>,
    );
    await waitFor(() =>
      expect(screen.getByTestId("authenticated").textContent).toBe("false"),
    );

    screen.getByText("Sign in").click();
    await waitFor(() =>
      expect(screen.getByTestId("authenticated").textContent).toBe("true"),
    );
    expect(screen.getByTestId("email").textContent).toBe(USER.university_email);
    expect(authApiMock.login).toHaveBeenCalledWith({
      university_email: "ayesha.khan@lgu.edu.pk",
      password: "StrongPass1!",
    });
  });

  it("logout clears the user even when the server call throws", async () => {
    authApiMock.getCurrentUser.mockResolvedValue(USER);
    authApiMock.logout.mockRejectedValue(new Error("server unreachable"));

    const LogoutHarness = () => {
      const { logout, isAuthenticated } = useAuth();
      return (
        <div>
          <button
            onClick={async () => {
              await logout();
            }}
          >
            Sign out
          </button>
          <p data-testid="authenticated">{String(isAuthenticated)}</p>
        </div>
      );
    };

    render(
      <AuthProvider>
        <LogoutHarness />
      </AuthProvider>,
    );
    await waitFor(() =>
      expect(screen.getByTestId("authenticated").textContent).toBe("true"),
    );

    screen.getByText("Sign out").click();
    await waitFor(() =>
      expect(screen.getByTestId("authenticated").textContent).toBe("false"),
    );
  });
});
