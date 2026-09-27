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
  type PasswordResetConfirm,
  type SessionListResponse,
} from "@uniserve/shared-types";

// ---- Web Token Storage ----

// Access token kept in module-scope memory — never persisted to DOM storage.
let inMemoryAccessToken: string | null = null;

const REFRESH_TOKEN_KEY = "uniserve_refresh_token";

// Lightweight session flag cookie — NOT proof of authentication.
// Used only by middleware as a routing hint to avoid redirecting pages
// when the browser definitely has no tokens. Real validation happens
// client-side in AuthContext via silent token refresh.
const SESSION_COOKIE = "uniserve_session";

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

/**
 * Set or clear the lightweight session flag cookie.
 * This is NOT authentication proof — it's a routing hint for middleware.
 * SameSite=Lax + path=/ so it's sent on normal navigations but not CSRF.
 * 7-day maxAge aligns with typical refresh token lifetimes.
 */
function setSessionCookie(active: boolean): void {
  if (typeof document === "undefined") return;
  if (active) {
    document.cookie = `${SESSION_COOKIE}=1; path=/; samesite=lax; max-age=${7 * 24 * 60 * 60}`;
  } else {
    document.cookie = `${SESSION_COOKIE}=; path=/; samesite=lax; max-age=0`;
  }
}

const webTokenProvider: TokenProvider = {
  getAccessToken: () => inMemoryAccessToken,
  getRefreshToken: () => readRefreshToken(),
  setTokens: (accessToken: string, refreshToken: string) => {
    inMemoryAccessToken = accessToken;
    writeRefreshToken(refreshToken);
    setSessionCookie(true);
  },
  clearTokens: () => {
    inMemoryAccessToken = null;
    writeRefreshToken(null);
    setSessionCookie(false);
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

export async function confirmPasswordReset(
  data: PasswordResetConfirm,
): Promise<{ message: string }> {
  return apiClient.post<{ message: string }>(
    "/auth/password/reset/confirm",
    data,
  );
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

// ---- Dashboard Data API Functions ----

export async function getCafeterias(): Promise<
  import("@uniserve/shared-types").Cafeteria[]
> {
  const response = await apiClient.get<
    { cafeterias: import("@uniserve/shared-types").Cafeteria[] }
  >("/cafeterias");
  return response.cafeterias ?? [];
}

export async function getOrders(params?: {
  status?: string;
  limit?: number;
}): Promise<import("@uniserve/shared-types").Order[]> {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.limit) query.set("limit", String(params.limit));
  const qs = query.toString();
  const response = await apiClient.get<{
    orders: import("@uniserve/shared-types").Order[];
    total: number;
  }>(`/orders${qs ? `?${qs}` : ""}`);
  return response.orders ?? [];
}

export async function getNotifications(params?: {
  is_read?: boolean;
  limit?: number;
}): Promise<import("@uniserve/shared-types").NotificationListResponse> {
  const query = new URLSearchParams();
  if (params?.is_read !== undefined)
    query.set("is_read", String(params.is_read));
  if (params?.limit) query.set("limit", String(params.limit));
  const qs = query.toString();
  return apiClient.get<import("@uniserve/shared-types").NotificationListResponse>(
    `/notifications${qs ? `?${qs}` : ""}`,
  );
}

export async function getUnreadNotificationCount(): Promise<
  import("@uniserve/shared-types").UnreadCountResponse
> {
  return apiClient.get<import("@uniserve/shared-types").UnreadCountResponse>(
    "/notifications/unread-count",
  );
}
