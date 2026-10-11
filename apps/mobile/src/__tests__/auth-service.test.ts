/**
 * Phase 60 (Workstream B) — Auth service contract tests.
 *
 * Covers the profile-adjacent auth surface (password change, PIN
 * enable/change/disable) plus login/PIN-login/logout/refresh endpoint
 * contracts used by AuthContext.
 */

jest.mock("../services/api", () => ({
  apiClient: {
    get: jest.fn(),
    post: jest.fn(),
    patch: jest.fn(),
    delete: jest.fn(),
  },
  secureStoreTokenProvider: {
    getAccessToken: jest.fn(() => null),
    getRefreshToken: jest.fn(() => null),
    setTokens: jest.fn(),
    clearTokens: jest.fn(),
  },
  loadPersistedTokens: jest.fn(),
  setOnAuthFailure: jest.fn(),
}));

import { apiClient, secureStoreTokenProvider } from "../services/api";
import {
  login,
  pinLogin,
  logout,
  refreshTokens,
  changePassword,
  enablePin,
  changePin,
  disablePin,
} from "../services/auth";

const apiMock = apiClient as jest.Mocked<typeof apiClient>;
const providerMock = secureStoreTokenProvider as jest.Mocked<
  typeof secureStoreTokenProvider
>;

beforeEach(() => {
  jest.clearAllMocks();
});

describe("auth service — login endpoints", () => {
  it("posts credentials to /auth/login", async () => {
    const response = { tokens: {}, user: {} };
    apiMock.post.mockResolvedValue(response);

    const result = await login({
      university_email: "s@lgu.edu.pk",
      password: "Pass123!",
    });

    expect(apiMock.post).toHaveBeenCalledWith("/auth/login", {
      university_email: "s@lgu.edu.pk",
      password: "Pass123!",
    });
    expect(result).toBe(response);
  });

  it("posts PIN credentials to /auth/pin/login", async () => {
    apiMock.post.mockResolvedValue({});

    await pinLogin({ user_id: "u1", pin: "1234" });

    expect(apiMock.post).toHaveBeenCalledWith("/auth/pin/login", {
      user_id: "u1",
      pin: "1234",
    });
  });

  it("posts to /auth/logout on logout", async () => {
    apiMock.post.mockResolvedValue(undefined);

    await logout();

    expect(apiMock.post).toHaveBeenCalledWith("/auth/logout");
  });
});

describe("auth service — token refresh", () => {
  it("throws locally when no refresh token is stored", async () => {
    providerMock.getRefreshToken.mockReturnValue(null);

    await expect(refreshTokens()).rejects.toThrow(
      "No refresh token available",
    );
    expect(apiMock.post).not.toHaveBeenCalled();
  });

  it("posts the stored refresh token to /auth/refresh", async () => {
    providerMock.getRefreshToken.mockReturnValue("refresh-1");
    apiMock.post.mockResolvedValue({});

    await refreshTokens();

    expect(apiMock.post).toHaveBeenCalledWith("/auth/refresh", {
      refresh_token: "refresh-1",
    });
  });
});

describe("auth service — profile password + PIN management", () => {
  it("posts password changes to /auth/password/change", async () => {
    apiMock.post.mockResolvedValue({ message: "ok" });

    await changePassword({
      current_password: "OldPass1!",
      new_password: "NewPass2!",
    });

    expect(apiMock.post).toHaveBeenCalledWith("/auth/password/change", {
      current_password: "OldPass1!",
      new_password: "NewPass2!",
    });
  });

  it("posts PIN enable/change/disable to their endpoints", async () => {
    apiMock.post.mockResolvedValue({ message: "ok" });

    await enablePin({
      current_password: "Pass123!",
      pin: "1234",
      confirm_pin: "1234",
    });
    expect(apiMock.post).toHaveBeenLastCalledWith("/auth/pin/enable", {
      current_password: "Pass123!",
      pin: "1234",
      confirm_pin: "1234",
    });

    await changePin({
      current_pin: "1234",
      new_pin: "5678",
      confirm_pin: "5678",
    });
    expect(apiMock.post).toHaveBeenLastCalledWith("/auth/pin/change", {
      current_pin: "1234",
      new_pin: "5678",
      confirm_pin: "5678",
    });

    await disablePin({ current_password: "Pass123!" });
    expect(apiMock.post).toHaveBeenLastCalledWith("/auth/pin/disable", {
      current_password: "Pass123!",
    });
  });
});
