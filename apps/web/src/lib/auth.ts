/**
 * UniServe — Web Authentication API Client
 */

import { API_BASE_URL } from "../lib/api";
import type {
  LoginRequest,
  LoginResponse,
  RegisterRequest,
  RegisterResponse,
  User,
  TokenPair,
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
      // ignore
    }
    throw new AuthApiError(
      errorBody.detail || `API Error: ${response.status}`,
      response.status,
      errorBody.code
    );
  }

  if (response.status === 204) return undefined as T;
  return response.json();
}

// ---- Auth API Functions ----

export async function login(data: LoginRequest): Promise<LoginResponse> {
  return apiRequest<LoginResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function register(data: RegisterRequest): Promise<RegisterResponse> {
  return apiRequest<RegisterResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function refreshTokens(refreshToken: string): Promise<TokenPair> {
  return apiRequest<TokenPair>("/auth/refresh", {
    method: "POST",
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
}

export async function getCurrentUser(token: string): Promise<User> {
  return apiRequest<User>("/auth/me", {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function logout(token: string): Promise<void> {
  await apiRequest("/auth/logout", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function requestPasswordReset(email: string): Promise<{ message: string }> {
  return apiRequest<{ message: string }>("/auth/password/reset/request", {
    method: "POST",
    body: JSON.stringify({ university_email: email }),
  });
}
