/**
 * UniServe — Web API Client
 *
 * Uses the shared ApiClient from @uniserve/shared-types.
 * Web-specific token provider stores access token in memory
 * (module-scope variable) and refresh token in sessionStorage.
 * This avoids localStorage for XSS mitigation.
 */

import {
  ApiClient,
  type TokenProvider,
  type TokenPair,
  type LoginRequest,
  type LoginResponse,
  type RegisterRequest,
  type RegisterResponse,
  type User,
  type OTPResponse,
  type OTPVerifyRequest,
  type OTPResendRequest,
  type PasswordResetRequest,
  type SessionListResponse,
} from "@uniserve/shared-types";

// ---- Web Token Storage ----

// Access token kept in module-scope memory — never persisted to DOM storage.
let inMemoryAccessToken: string | null = null;

const REFRESH_TOKEN_KEY = "uniserve_refresh_token";

function readRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return sessionStorage.getItem(REFRESH_TOKEN_KEY);
  } catch {
    return null;
  }
}

function writeRefreshToken(token: string | null): void {
  if (typeof window === "undefined") return;
  try {
    if (token) {
      sessionStorage.setItem(REFRESH_TOKEN_KEY, token);
    } else {
      sessionStorage.removeItem(REFRESH_TOKEN_KEY);
    }
  } catch {
    // sessionStorage unavailable — degrade silently
  }
}

const webTokenProvider: TokenProvider = {
  getAccessToken: () => inMemoryAccessToken,
  getRefreshToken: () => readRefreshToken(),
  setTokens: (accessToken: string, refreshToken: string) => {
    inMemoryAccessToken = accessToken;
    writeRefreshToken(refreshToken);
  },
  clearTokens: () => {
    inMemoryAccessToken = null;
    writeRefreshToken(null);
  },
};

// ---- Client Initialization ----

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

let onAuthFailureCallback: (() => void) | null = null;

export function setOnAuthFailure(callback: () => void): void {
  onAuthFailureCallback = callback;
}

export const apiClient = new ApiClient(
  API_BASE_URL,
  webTokenProvider,
  () => onAuthFailureCallback?.(),
);

// ---- Auth API Functions (use shared client) ----

export async function login(data: LoginRequest): Promise<LoginResponse> {
  const response = await apiClient.post<LoginResponse>("/auth/login", data);
  // Store tokens immediately after successful login
  webTokenProvider.setTokens(
    response.tokens.access_token,
    response.tokens.refresh_token,
  );
  return response;
}

export async function register(
  data: RegisterRequest,
): Promise<RegisterResponse> {
  return apiClient.post<RegisterResponse>("/auth/register", data);
}

export async function getCurrentUser(): Promise<User> {
  return apiClient.get<User>("/auth/me");
}

export async function logout(): Promise<void> {
  try {
    await apiClient.post("/auth/logout");
  } finally {
    webTokenProvider.clearTokens();
  }
}

export async function requestPasswordReset(
  data: PasswordResetRequest,
): Promise<{ message: string }> {
  return apiClient.post<{ message: string }>(
    "/auth/password/reset/request",
    data,
  );
}

export async function verifyOtp(
  data: OTPVerifyRequest,
): Promise<OTPResponse> {
  return apiClient.post<OTPResponse>("/auth/otp/verify", data);
}

export async function resendOtp(
  data: OTPResendRequest,
): Promise<OTPResponse> {
  return apiClient.post<OTPResponse>("/auth/otp/resend", data);
}

export async function refreshTokens(): Promise<TokenPair> {
  const refreshToken = webTokenProvider.getRefreshToken();
  if (!refreshToken) throw new Error("No refresh token available");
  const response = await apiClient.post<TokenPair>("/auth/refresh", {
    refresh_token: refreshToken,
  });
  webTokenProvider.setTokens(
    response.access_token,
    response.refresh_token,
  );
  return response;
}

export async function getSessions(): Promise<SessionListResponse> {
  return apiClient.get<SessionListResponse>("/auth/sessions");
}

// Re-export shared types for convenience
export { ApiClientError } from "@uniserve/shared-types";
