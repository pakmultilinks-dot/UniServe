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

// ── Operations Console API ──────────────────────────────────────

// Orders — Staff/Manager queue
export async function getCafeteriaOrders(
  cafeteriaId: string,
  params?: { status?: string; order_date?: string },
) {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.order_date) query.set("order_date", params.order_date);
  const qs = query.toString();
  return apiClient.get<{ orders: any[]; total: number }>(
    `/orders/cafeteria/${cafeteriaId}${qs ? `?${qs}` : ""}`,
  );
}

export async function getOrderDetail(orderId: string) {
  return apiClient.get<any>(`/orders/${orderId}`);
}

export async function confirmOrder(orderId: string, notes?: string) {
  return apiClient.post<any>(`/orders/${orderId}/confirm`, { notes });
}

export async function prepareOrder(orderId: string, notes?: string) {
  return apiClient.post<any>(`/orders/${orderId}/prepare`, { notes });
}

export async function readyOrder(orderId: string, notes?: string) {
  return apiClient.put<any>(`/orders/${orderId}/ready`, { notes });
}

export async function delayOrder(
  orderId: string,
  additionalMinutes: number,
  notes?: string,
) {
  return apiClient.put<any>(`/orders/${orderId}/delay`, {
    additional_minutes: additionalMinutes,
    notes,
  });
}

export async function managerCancelOrder(orderId: string, reason: string) {
  return apiClient.post<any>(`/orders/${orderId}/manager-cancel`, { reason });
}

export async function rejectOrder(
  orderId: string,
  reason: string,
  notes?: string,
) {
  return apiClient.post<any>(`/orders/${orderId}/reject`, { reason, notes });
}

export async function collectOrder(params: {
  order_number?: number;
  collection_token?: string;
}) {
  return apiClient.post<any>("/orders/collect", params);
}

// Menu management
export async function getMenuItems(
  cafeteriaId: string,
  params?: { category?: string; is_available?: boolean; search?: string },
) {
  const query = new URLSearchParams();
  if (params?.category) query.set("category", params.category);
  if (params?.is_available !== undefined)
    query.set("is_available", String(params.is_available));
  if (params?.search) query.set("search", params.search);
  const qs = query.toString();
  return apiClient.get<{ items: any[]; total: number }>(
    `/cafeterias/${cafeteriaId}/menu-items${qs ? `?${qs}` : ""}`,
  );
}

export async function createMenuItem(cafeteriaId: string, data: any) {
  return apiClient.post<any>(
    `/cafeterias/${cafeteriaId}/menu-items/`,
    data,
  );
}

export async function updateMenuItem(
  cafeteriaId: string,
  itemId: string,
  data: any,
) {
  return apiClient.put<any>(
    `/cafeterias/${cafeteriaId}/menu-items/${itemId}`,
    data,
  );
}

// Daily menus
export async function getDailyMenus(cafeteriaId: string, status?: string) {
  const qs = status ? `?status=${status}` : "";
  return apiClient.get<any>(
    `/cafeterias/${cafeteriaId}/daily-menus${qs}`,
  );
}

export async function getTodayMenu(cafeteriaId: string) {
  return apiClient.get<any>(
    `/cafeterias/${cafeteriaId}/daily-menus/today`,
  );
}

export async function createDailyMenu(cafeteriaId: string, menuDate: string) {
  return apiClient.post<any>(
    `/cafeterias/${cafeteriaId}/daily-menus/`,
    { menu_date: menuDate },
  );
}

export async function addDailyMenuItem(
  cafeteriaId: string,
  dailyMenuId: string,
  data: any,
) {
  return apiClient.post<any>(
    `/cafeterias/${cafeteriaId}/daily-menus/${dailyMenuId}/items`,
    data,
  );
}

export async function publishDailyMenu(cafeteriaId: string, dailyMenuId: string) {
  return apiClient.patch<any>(
    `/cafeterias/${cafeteriaId}/daily-menus/${dailyMenuId}/publish`,
  );
}

// Inventory
export async function getInventory(cafeteriaId: string, lowOnly?: boolean) {
  const qs = lowOnly ? "?low_only=true" : "";
  return apiClient.get<{ items: any[]; total: number }>(
    `/cafeterias/${cafeteriaId}/inventory${qs}`,
  );
}

export async function adjustInventory(
  cafeteriaId: string,
  data: { inventory_item_id: string; adjustment_quantity: number; reason?: string },
) {
  return apiClient.post<any>(
    `/cafeterias/${cafeteriaId}/inventory/adjust`,
    data,
  );
}

// Users (Admin)
export async function getUsers(params?: { role?: string; status?: string }) {
  const query = new URLSearchParams();
  if (params?.role) query.set("role", params.role);
  if (params?.status) query.set("status", params.status);
  const qs = query.toString();
  return apiClient.get<any[]>(`/users${qs ? `?${qs}` : ""}`);
}

export async function getUserDetail(userId: string) {
  return apiClient.get<any>(`/users/${userId}`);
}

export async function suspendUser(userId: string, reason: string) {
  return apiClient.post<any>(`/users/${userId}/suspend`, { reason });
}

export async function activateUser(userId: string) {
  return apiClient.post<any>(`/users/${userId}/activate`);
}

export async function changeUserRole(
  userId: string,
  role: string,
  cafeteriaId?: string,
) {
  return apiClient.put<any>(`/users/${userId}/role`, {
    role,
    cafeteria_id: cafeteriaId,
  });
}

// Administration overview
export async function getAdministrationOverview(params?: {
  start_date?: string;
  end_date?: string;
}) {
  const query = new URLSearchParams();
  if (params?.start_date) query.set("start_date", params.start_date);
  if (params?.end_date) query.set("end_date", params.end_date);
  const qs = query.toString();
  return apiClient.get<any>(`/administration/overview${qs ? `?${qs}` : ""}`);
}

// Reports
export async function getSalesReport(params?: {
  start_date?: string;
  end_date?: string;
  cafeteria_id?: string;
}) {
  const query = new URLSearchParams();
  if (params?.start_date) query.set("start_date", params.start_date);
  if (params?.end_date) query.set("end_date", params.end_date);
  if (params?.cafeteria_id) query.set("cafeteria_id", params.cafeteria_id);
  const qs = query.toString();
  return apiClient.get<any>(`/reports/sales${qs ? `?${qs}` : ""}`);
}

export async function getDailySalesReport(params?: {
  start_date?: string;
  end_date?: string;
  cafeteria_id?: string;
}) {
  const query = new URLSearchParams();
  if (params?.start_date) query.set("start_date", params.start_date);
  if (params?.end_date) query.set("end_date", params.end_date);
  if (params?.cafeteria_id) query.set("cafeteria_id", params.cafeteria_id);
  const qs = query.toString();
  return apiClient.get<any>(`/reports/sales/daily${qs ? `?${qs}` : ""}`);
}

export async function getOrderSummaryReport(params?: {
  start_date?: string;
  end_date?: string;
  cafeteria_id?: string;
}) {
  const query = new URLSearchParams();
  if (params?.start_date) query.set("start_date", params.start_date);
  if (params?.end_date) query.set("end_date", params.end_date);
  if (params?.cafeteria_id) query.set("cafeteria_id", params.cafeteria_id);
  const qs = query.toString();
  return apiClient.get<any>(`/reports/orders/summary${qs ? `?${qs}` : ""}`);
}

// Refunds (Admin)
export async function getAllRefunds(params?: {
  cafeteria_id?: string;
  status?: string;
  limit?: number;
  offset?: number;
}) {
  const query = new URLSearchParams();
  if (params?.cafeteria_id) query.set("cafeteria_id", params.cafeteria_id);
  if (params?.status) query.set("status", params.status);
  if (params?.limit) query.set("limit", String(params.limit));
  if (params?.offset) query.set("offset", String(params.offset));
  const qs = query.toString();
  return apiClient.get<{ refunds: any[]; total: number }>(
    `/refunds/admin/all${qs ? `?${qs}` : ""}`,
  );
}

export async function processRefund(refundId: string, body?: { action?: string; reason?: string }) {
  return apiClient.post<any>(`/refunds/${refundId}/process`, body);
}

// Notifications
export async function markNotificationRead(notificationId: string) {
  return apiClient.patch<any>(`/notifications/${notificationId}/read`);
}

export async function markAllNotificationsRead() {
  return apiClient.patch<any>("/notifications/read-all");
}

// Cafeteria status
export async function updateCafeteriaStatus(
  cafeteriaId: string,
  status: string,
) {
  return apiClient.patch<any>(`/cafeterias/${cafeteriaId}/status`, {
    status,
  });
}

export async function updateCafeteria(
  cafeteriaId: string,
  data: any,
) {
  return apiClient.put<any>(`/cafeterias/${cafeteriaId}`, data);
}
