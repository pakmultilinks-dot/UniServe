/**
 * UniServe — Authentication API Service
 *
 * All authentication-related API calls.
 * Uses the shared ApiClient for consistent error handling and auth injection.
 */

import { apiClient, secureStoreTokenProvider } from "./api";
import type {
  LoginRequest,
  LoginResponse,
  RegisterRequest,
  RegisterResponse,
  OTPVerifyRequest,
  OTPResendRequest,
  OTPResponse,
  PINLoginRequest,
  PINSetupRequest,
  PINChangeRequest,
  PINDisableRequest,
  TokenPair,
  User,
  PasswordResetRequest,
  PasswordResetConfirm,
  PasswordChangeRequest,
} from "@uniserve/shared-types";

// ---- Registration ----

export async function register(data: RegisterRequest): Promise<RegisterResponse> {
  return apiClient.post<RegisterResponse>("/auth/register", data);
}

// ---- OTP ----

export async function verifyOtp(data: OTPVerifyRequest): Promise<OTPResponse> {
  return apiClient.post<OTPResponse>("/auth/otp/verify", data);
}

export async function resendOtp(data: OTPResendRequest): Promise<OTPResponse> {
  return apiClient.post<OTPResponse>("/auth/otp/resend", data);
}

// ---- Login ----

// A sleeping free Render instance can take roughly a minute to wake.
// Auth must wait longer than the shared 60-second request timeout without
// changing timeouts for non-idempotent checkout or payment endpoints.
export const AUTH_LOGIN_TIMEOUT_MS = 125_000;

export async function login(data: LoginRequest): Promise<LoginResponse> {
  return apiClient.request<LoginResponse>("POST", "/auth/login", {
    body: data,
    timeout: AUTH_LOGIN_TIMEOUT_MS,
  });
}

export async function pinLogin(data: PINLoginRequest): Promise<LoginResponse> {
  return apiClient.request<LoginResponse>("POST", "/auth/pin/login", {
    body: data,
    timeout: AUTH_LOGIN_TIMEOUT_MS,
  });
}

// ---- Token Management ----

export async function refreshTokens(): Promise<TokenPair> {
  const refreshToken = secureStoreTokenProvider.getRefreshToken();
  if (!refreshToken) throw new Error("No refresh token available");
  return apiClient.post<TokenPair>("/auth/refresh", {
    refresh_token: refreshToken,
  });
}

// ---- Current User ----

export async function getCurrentUser(): Promise<User> {
  return apiClient.get<User>("/auth/me");
}

// ---- Logout ----

export async function logout(): Promise<void> {
  await apiClient.post("/auth/logout");
}

export async function logoutAll(): Promise<void> {
  await apiClient.post("/auth/logout-all");
}

// ---- Password ----

export async function requestPasswordReset(
  data: PasswordResetRequest,
): Promise<{ message: string }> {
  return apiClient.post<{ message: string }>(
    "/auth/password/reset/request",
    data,
  );
}

export async function resetPassword(
  data: PasswordResetConfirm,
): Promise<{ message: string }> {
  return apiClient.post<{ message: string }>(
    "/auth/password/reset/confirm",
    data,
  );
}

export async function changePassword(
  data: PasswordChangeRequest,
): Promise<{ message: string }> {
  return apiClient.post<{ message: string }>(
    "/auth/password/change",
    data,
  );
}

// ---- PIN Management (Phase 58, Workstream F+G) ----

export async function enablePin(
  data: PINSetupRequest,
): Promise<{ message: string }> {
  return apiClient.post<{ message: string }>(
    "/auth/pin/enable",
    data,
  );
}

export async function changePin(
  data: PINChangeRequest,
): Promise<{ message: string }> {
  return apiClient.post<{ message: string }>(
    "/auth/pin/change",
    data,
  );
}

export async function disablePin(
  data: PINDisableRequest,
): Promise<{ message: string }> {
  return apiClient.post<{ message: string }>(
    "/auth/pin/disable",
    data,
  );
}
