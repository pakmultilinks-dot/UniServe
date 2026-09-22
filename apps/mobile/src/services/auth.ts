/**
 * UniServe — Authentication API Service
 *
 * All authentication-related API calls.
 */

import { API_BASE_URL } from "../config";
import type {
  LoginRequest,
  LoginResponse,
  RegisterRequest,
  RegisterResponse,
  OTPVerifyRequest,
  OTPResendRequest,
  OTPResponse,
  PINLoginRequest,
  RefreshTokenRequest,
  TokenPair,
  PasswordResetRequest,
  PasswordResetConfirm,
  PasswordChangeRequest,
  User,
  SessionListResponse,
} from "../types/auth";

class AuthApiError extends Error {
  status: number;
  code?: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "AuthApiError";
    this.status = status;
    this.code = code;
  }
}

async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!response.ok) {
    let errorBody: { detail?: string; code?: string } = {};
    try {
      errorBody = await response.json();
    } catch {
      // ignore parse errors
    }
    throw new AuthApiError(
      errorBody.detail || `API Error: ${response.status}`,
      response.status,
      errorBody.code
    );
  }

  // 204 No Content
  if (response.status === 204) return undefined as T;

  return response.json();
}

// ---- Registration ----

export async function register(data: RegisterRequest): Promise<RegisterResponse> {
  return apiRequest<RegisterResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ---- OTP ----

export async function verifyOtp(data: OTPVerifyRequest): Promise<OTPResponse> {
  return apiRequest<OTPResponse>("/auth/otp/verify", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function resendOtp(data: OTPResendRequest): Promise<OTPResponse> {
  return apiRequest<OTPResponse>("/auth/otp/resend", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ---- Login ----

export async function login(data: LoginRequest): Promise<LoginResponse> {
  return apiRequest<LoginResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function pinLogin(data: PINLoginRequest): Promise<LoginResponse> {
  return apiRequest<LoginResponse>("/auth/pin/login", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ---- Token Management ----

export async function refreshTokens(refreshToken: string): Promise<TokenPair> {
  return apiRequest<TokenPair>("/auth/refresh", {
    method: "POST",
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
}

// ---- Current User ----

export async function getCurrentUser(token: string): Promise<User> {
  return apiRequest<User>("/auth/me", {
    headers: { Authorization: `Bearer ${token}` },
  });
}

// ---- Sessions ----

export async function getSessions(token: string): Promise<SessionListResponse> {
  return apiRequest<SessionListResponse>("/auth/sessions", {
    headers: { Authorization: `Bearer ${token}` },
  });
}

// ---- Logout ----

export async function logout(token: string): Promise<{ message: string }> {
  return apiRequest<{ message: string }>("/auth/logout", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function logoutAll(token: string): Promise<{ message: string }> {
  return apiRequest<{ message: string }>("/auth/logout-all", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}

// ---- Password ----

export async function requestPasswordReset(
  email: string
): Promise<{ message: string }> {
  return apiRequest<{ message: string }>("/auth/password/reset/request", {
    method: "POST",
    body: JSON.stringify({ university_email: email }),
  });
}

export async function resetPassword(
  data: PasswordResetConfirm
): Promise<{ message: string }> {
  return apiRequest<{ message: string }>("/auth/password/reset/confirm", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function changePassword(
  token: string,
  data: PasswordChangeRequest
): Promise<{ message: string }> {
  return apiRequest<{ message: string }>("/auth/password/change", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify(data),
  });
}
