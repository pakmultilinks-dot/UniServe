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
  ApiClientError,
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
  type AdminCreateUserRequest,
  type AdminCreateUserResponse,
  type AdminChangeRoleRequest,
  type AdminSuspendRequest,
  type SalesReportResponse,
  type SalesDailyResponse,
  type SalesByCafeteriaResponse,
  type OrderSummaryResponse,
  type OrderVolumeResponse,
  type CancellationRateResponse,
  type CafeteriaPopularItemsResponse,
  type CafeteriaPerformanceResponse,
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

/** P3-3 — return the cafeteria IDs the current staff/manager user is
 * assigned to (empty for admin / students / faculty). Used to default
 * cafeteria selectors to the user's actual assignment. */
export async function getMyCafeterias(): Promise<string[]> {
  try {
    const response = await apiClient.get<{ cafeteria_ids: string[] }>(
      "/auth/me/cafeterias",
    );
    return response.cafeteria_ids ?? [];
  } catch {
    // Older deployments or unexpected errors — fall back to no assignment
    // info so pages behave exactly as before (first cafeteria selected).
    return [];
  }
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

// ---- Phase 55 — Admin Self-Service & Settings Foundation ----

export interface AuditEvent {
  id: number;
  event_type: string;
  user_id: string | null;
  user_name: string | null;
  description: string | null;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
}

export interface AuditEventListResponse {
  events: AuditEvent[];
  total: number;
}

export interface UserListResponse {
  users: User[];
  total: number;
}

export interface AccountRecoveryResponse {
  message: string;
  temporary_password: string;
}

/** Sign out of ALL sessions, including the current one. The server
 * revokes every refresh token; local state is always cleared so the
 * client cannot keep using a revoked access token after the refresh. */
export async function logoutAll(): Promise<{ message: string }> {
  try {
    return await apiClient.post<{ message: string }>("/auth/logout-all");
  } finally {
    webTokenProvider.clearTokens();
  }
}

/** Change the authenticated user's password (current_password required). */
export async function changePassword(data: {
  current_password: string;
  new_password: string;
}): Promise<{ message: string }> {
  return apiClient.post<{ message: string }>("/auth/password/change", data);
}

/** P55 — profile self-update (first_name/last_name only, self-scoped).
 * Returns the updated user; no sensitive values are echoed. */
export async function updateProfile(data: {
  first_name?: string;
  last_name?: string;
}): Promise<User> {
  return apiClient.patch<User>("/auth/me", data);
}

/** P55 — admin audit log (University Admin only, newest first). */
export async function getAuditEvents(params?: {
  limit?: number;
  offset?: number;
  event_type?: string;
}): Promise<AuditEventListResponse> {
  const query = new URLSearchParams();
  if (params?.limit != null) query.set("limit", String(params.limit));
  if (params?.offset != null) query.set("offset", String(params.offset));
  if (params?.event_type) query.set("event_type", params.event_type);
  const qs = query.toString();
  return apiClient.get<AuditEventListResponse>(
    `/administration/audit-events${qs ? `?${qs}` : ""}`,
  );
}

/** P55 — admin account recovery: resets the credential to a one-time
 * temporary password, clears lockout counters, reactivates suspended
 * accounts. `university_id` is an identity confirmation required by the
 * API; the temporary password is returned exactly once. */
export async function recoverUser(
  userId: string,
  data: { university_id: string; reason?: string },
): Promise<AccountRecoveryResponse> {
  return apiClient.post<AccountRecoveryResponse>(
    `/users/${userId}/recover`,
    data,
  );
}

// Re-export shared types for convenience
export { ApiClientError };

// ---- Dashboard Data API Functions ----

// Phase 56 — optional is_active filter. Backend GET /cafeterias accepts
// ?is_active=true|false; omitting the param preserves the historical
// "all cafeterias" behaviour (admin management + historical reports).
// Operational selectors (menu, inventory, orders, staff, home ordering,
// broadcast targeting) call this with { isActive: true }.
export async function getCafeterias(options?: {
  isActive?: boolean;
}): Promise<import("@uniserve/shared-types").Cafeteria[]> {
  const qs =
    options?.isActive !== undefined
      ? `?is_active=${String(options.isActive)}`
      : "";
  const response = await apiClient.get<
    { cafeterias: import("@uniserve/shared-types").Cafeteria[] }
  >(`/cafeterias${qs}`);
  return response.cafeterias ?? [];
}

/** 48A — create a cafeteria (University Admin only, enforced by the API). */
export async function createCafeteria(
  data: import("@uniserve/shared-types").CafeteriaCreate,
): Promise<import("@uniserve/shared-types").Cafeteria> {
  return apiClient.post<import("@uniserve/shared-types").Cafeteria>(
    "/cafeterias/",
    data,
  );
}

export async function getOrders(params?: {
  status?: string;
}): Promise<import("@uniserve/shared-types").Order[]> {
  // Backend GET /orders accepts only cafeteria_id/status/days — a `limit`
  // param was never supported and was silently ignored.
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  const qs = query.toString();
  const response = await apiClient.get<{
    orders: import("@uniserve/shared-types").Order[];
    total: number;
  }>(`/orders${qs ? `?${qs}` : ""}`);
  return response.orders ?? [];
}

export async function getNotifications(params?: {
  unread_only?: boolean;
  limit?: number;
}): Promise<import("@uniserve/shared-types").NotificationListResponse> {
  const query = new URLSearchParams();
  if (params?.unread_only !== undefined)
    query.set("unread_only", String(params.unread_only));
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
  params?: {
    status?: string;
    order_date?: string;
    // Phase 54 — queue pagination (backend GET /orders/cafeteria/{id});
    // omit both to preserve the original unpaginated behaviour.
    limit?: number;
    offset?: number;
  },
) {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.order_date) query.set("order_date", params.order_date);
  if (params?.limit) query.set("limit", String(params.limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
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

// Phase 54 — Manager Cancel Order (backend: POST /orders/{id}/manager-cancel).
// Backend RBAC: cafeteria_manager only, assigned cafeteria only; eligible
// statuses pending/preparing; the cancellation reason is OPTIONAL server-side
// (OrderCancelRequest.reason: str | None) — no reason field is collected.
export async function managerCancelOrder(orderId: string, reason?: string) {
  return apiClient.post<any>(`/orders/${orderId}/manager-cancel`, {
    reason: reason ?? null,
  });
}

// ── Phase 58 (Workstream E) ──────────────────────────────────────────────

// Close Day — manager-only sudden cafeteria close (backend:
// POST /orders/cafeteria/{id}/close). Backend RBAC: cafeteria_manager only,
// assigned cafeteria only; cancels PENDING + PREPARING orders, releases
// their inventory reservations, and sets the cafeteria operational_status
// to CLOSED. Returns the list of cancelled orders (OrderListResponse:
// { orders, total }) — an empty list means nothing was open to cancel.
export async function closeCafeteriaDay(
  cafeteriaId: string,
  notes?: string,
): Promise<{ orders: Array<{ id: string; order_number: string }>; total: number }> {
  return apiClient.post(`/orders/cafeteria/${cafeteriaId}/close`, {
    notes: notes || null,
  });
}

// Computed ETA — backend: GET /orders/{id}/eta (owner, admin, or assigned
// cafeteria manager/staff; server-side authorization is enforced — a
// non-owner non-assigned caller receives "Order not found"). eta_minutes is
// computed by the backend from live cafeteria preparation times.
export async function getOrderEta(orderId: string): Promise<{
  order_id: string;
  eta_minutes: number;
  pickup_deadline?: string | null;
}> {
  return apiClient.get(`/orders/${orderId}/eta`);
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

/** Phase 56 — soft-delete a menu item (admin-only on the backend).
 * The item flips to inactive/unavailable; historical daily menus, order
 * snapshots and reports are unaffected. */
export async function deleteMenuItem(cafeteriaId: string, itemId: string) {
  return apiClient.delete<any>(
    `/cafeterias/${cafeteriaId}/menu-items/${itemId}`,
  );
}

// Daily menus
export async function getDailyMenus(cafeteriaId: string, status?: string) {
  const qs = status ? `?status=${status}` : "";
  return apiClient.get<any>(
    `/cafeterias/${cafeteriaId}/daily-menus${qs}`,
  );
}

export async function createDailyMenu(cafeteriaId: string, menuDate: string) {
  return apiClient.post<any>(
    `/cafeterias/${cafeteriaId}/daily-menus/`,
    { menu_date: menuDate },
  );
}

/** Phase 56 — copy a previous day's menu into a new draft.
 * Backend creates a NEW draft on the target date carrying over junction
 * metadata; an occupied target date produces an explicit 409 conflict —
 * copying never silently overwrites. Inactive menu items are skipped. */
export async function copyDailyMenu(
  cafeteriaId: string,
  data: { source_date: string; target_date: string },
) {
  return apiClient.post<any>(
    `/cafeterias/${cafeteriaId}/daily-menus/copy`,
    data,
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

/** WS4 — unpublish today's published daily menu (archives it, removes it
 * from customer lookups, preserves items). A replacement draft can then be
 * created for the same date. Manager/admin write scope on the backend. */
export async function unpublishDailyMenu(
  cafeteriaId: string,
  dailyMenuId: string,
) {
  return apiClient.patch<any>(
    `/cafeterias/${cafeteriaId}/daily-menus/${dailyMenuId}/unpublish`,
  );
}

export async function removeDailyMenuItem(
  cafeteriaId: string,
  dailyMenuId: string,
  menuItemId: string,
) {
  return apiClient.delete<any>(
    `/cafeterias/${cafeteriaId}/daily-menus/${dailyMenuId}/items/${menuItemId}`,
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

/** Phase 56 — create an inventory record for a menu item (manager/admin
 * write scope on the backend). Upsert semantics server-side: exactly one
 * record per (menu_item, cafeteria). */
export async function createInventoryItem(
  cafeteriaId: string,
  data: {
    menu_item_id: string;
    quantity: number;
    unit: string;
    low_threshold: number;
  },
) {
  return apiClient.post<any>(
    `/cafeterias/${cafeteriaId}/inventory/`,
    data,
  );
}

// Users (Admin) — Phase 47: typed wrappers for member & staff management.
// Backend responses include cafeteria_id/cafeteria_name on admin endpoints.
export async function getUsers(params?: { role?: string; status?: string }): Promise<User[]> {
  const query = new URLSearchParams();
  if (params?.role) query.set("role", params.role);
  if (params?.status) query.set("status", params.status);
  const qs = query.toString();
  return apiClient.get<User[]>(`/users${qs ? `?${qs}` : ""}`);
}

/** P55 — paginated users list (University Admin). Uses the backend's
 * limit/offset capability and always receives the { users, total }
 * envelope; `getUsers` above keeps the bare-list shape for existing
 * callers. */
export async function getUsersPaginated(params?: {
  role?: string;
  status?: string;
  q?: string;
  cafeteria_id?: string;
  limit?: number;
  offset?: number;
}): Promise<UserListResponse> {
  const query = new URLSearchParams();
  if (params?.role) query.set("role", params.role);
  if (params?.status) query.set("status", params.status);
  if (params?.q) query.set("q", params.q);
  if (params?.cafeteria_id) query.set("cafeteria_id", params.cafeteria_id);
  if (params?.limit != null) query.set("limit", String(params.limit));
  if (params?.offset != null) query.set("offset", String(params.offset));
  const qs = query.toString();
  return apiClient.get<UserListResponse>(`/users${qs ? `?${qs}` : ""}`);
}

export async function getUserDetail(userId: string): Promise<User> {
  return apiClient.get<User>(`/users/${userId}`);
}

/** Admin creates a member/staff account. Returns the one-time password. */
export async function createUser(
  data: AdminCreateUserRequest,
): Promise<AdminCreateUserResponse> {
  return apiClient.post<AdminCreateUserResponse>("/users/", data);
}

export async function suspendUser(
  userId: string,
  reason: string,
): Promise<User> {
  return apiClient.post<User>(`/users/${userId}/suspend`, {
    reason,
  } satisfies AdminSuspendRequest);
}

export async function activateUser(userId: string): Promise<User> {
  return apiClient.post<User>(`/users/${userId}/activate`);
}

export async function changeUserRole(
  userId: string,
  role: User["role"],
  cafeteriaId?: string,
): Promise<User> {
  return apiClient.put<User>(`/users/${userId}/role`, {
    role,
    cafeteria_id: cafeteriaId,
  } satisfies AdminChangeRoleRequest);
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
  const raw = await apiClient.get<any>(`/administration/overview${qs ? `?${qs}` : ""}`);
  // Map nested backend response to flat frontend shape
  return {
    total_users: raw.users?.total ?? 0,
    users_by_role: {
      student: raw.users?.students ?? 0,
      faculty: raw.users?.faculty ?? 0,
      cafeteria_manager: raw.users?.cafeteria_managers ?? 0,
      cafeteria_staff: raw.users?.cafeteria_staff ?? 0,
      university_admin: raw.users?.university_admins ?? 0,
    },
    total_orders: raw.orders?.total_orders ?? 0,
    orders_by_status: {
      pending: raw.orders?.pending ?? 0,
      preparing: raw.orders?.preparing ?? 0,
      ready: raw.orders?.ready ?? 0,
      completed: raw.orders?.completed ?? 0,
      cancelled: raw.orders?.cancelled ?? 0,
    },
    total_revenue: (raw.financial?.total_revenue ?? 0) / 100, // paisa -> rupees
    active_cafeterias: raw.cafeterias?.active ?? 0,
    // Phase 55 (design decision A) — the backend value is the honest
    // "overdue_refunds" count (pending/processing refunds older than 7
    // days). Renamed from the previous misleading "pending_refunds".
    overdue_refunds: raw.exceptions?.overdue_refunds ?? 0,
    total_menu_items: raw.menu_items ?? 0,
  };
}

// Reports — Phase 49: typed wrappers on the existing /reports endpoints.
// All money values are in paisa unless noted. Error handling flows through
// ApiClient (ApiClientError with status); wrappers do not swallow errors.

export interface ReportRangeParams {
  start_date?: string;
  end_date?: string;
  cafeteria_id?: string;
}

/** Flat sales-summary shape consumed by the reports dashboard (money in paisa). */
export interface SalesReportSummary {
  total_orders: number;
  total_revenue: number;
  net_revenue: number;
  total_refunded: number;
  online_payment_volume: number;
  cash_payment_volume: number;
}

function reportQuery(params?: ReportRangeParams): string {
  const query = new URLSearchParams();
  if (params?.start_date) query.set("start_date", params.start_date);
  if (params?.end_date) query.set("end_date", params.end_date);
  if (params?.cafeteria_id) query.set("cafeteria_id", params.cafeteria_id);
  const qs = query.toString();
  return qs ? `?${qs}` : "";
}

export async function getSalesReport(
  params?: ReportRangeParams,
): Promise<SalesReportSummary> {
  const raw = await apiClient.get<SalesReportResponse>(`/reports/sales${reportQuery(params)}`);
  // Backend returns SalesReportResponse { summary: {...}, currency } with all
  // money in paisa. Unwrap the summary here so callers receive a flat shape.
  const summary = raw?.summary;
  return {
    total_orders: summary?.total_orders ?? 0,
    total_revenue: summary?.total_revenue ?? 0,
    net_revenue: summary?.net_revenue ?? 0,
    total_refunded: summary?.total_refunded ?? 0,
    online_payment_volume: summary?.online_payment_volume ?? 0,
    cash_payment_volume: summary?.cash_payment_volume ?? 0,
  };
}

export async function getDailySalesReport(
  params?: ReportRangeParams,
): Promise<SalesDailyResponse> {
  return apiClient.get<SalesDailyResponse>(`/reports/sales/daily${reportQuery(params)}`);
}

export async function getSalesByCafeteriaReport(
  params?: { start_date?: string; end_date?: string },
): Promise<SalesByCafeteriaResponse> {
  return apiClient.get<SalesByCafeteriaResponse>(
    `/reports/sales/by-cafeteria${reportQuery(params)}`,
  );
}

export async function getOrderSummaryReport(
  params?: ReportRangeParams,
): Promise<OrderSummaryResponse> {
  return apiClient.get<OrderSummaryResponse>(
    `/reports/orders/summary${reportQuery(params)}`,
  );
}

export async function getOrderVolumeReport(
  params?: ReportRangeParams,
): Promise<OrderVolumeResponse> {
  return apiClient.get<OrderVolumeResponse>(
    `/reports/orders/volume${reportQuery(params)}`,
  );
}

export async function getCancellationRateReport(
  params?: ReportRangeParams,
): Promise<CancellationRateResponse> {
  return apiClient.get<CancellationRateResponse>(
    `/reports/orders/cancellation-rate${reportQuery(params)}`,
  );
}

export async function getPopularItemsReport(
  cafeteriaId: string,
  params?: { start_date?: string; end_date?: string; limit?: number },
): Promise<CafeteriaPopularItemsResponse> {
  const query = new URLSearchParams();
  if (params?.start_date) query.set("start_date", params.start_date);
  if (params?.end_date) query.set("end_date", params.end_date);
  if (params?.limit) query.set("limit", String(params.limit));
  const qs = query.toString();
  return apiClient.get<CafeteriaPopularItemsResponse>(
    `/reports/cafeteria/${cafeteriaId}/popular-items${qs ? `?${qs}` : ""}`,
  );
}

export async function getCafeteriaPerformanceReport(
  cafeteriaId: string,
  params?: { start_date?: string; end_date?: string },
): Promise<CafeteriaPerformanceResponse> {
  return apiClient.get<CafeteriaPerformanceResponse>(
    `/reports/cafeteria/${cafeteriaId}/performance${reportQuery(params)}`,
  );
}

// ── Phase 58 (Workstream C) — previously unwired report endpoints ──
// All four are cafeteria-scoped (backend requires cafeteria_id + assignment
// check; admin passes automatically). Response shapes are the backend's
// authoritative shared types — no reinterpretation.

/** Current stock snapshot for one cafeteria (no date range on the backend). */
export async function getInventoryStockLevelsReport(
  cafeteriaId: string,
): Promise<import("@uniserve/shared-types").InventoryStockLevelsResponse> {
  return apiClient.get<import("@uniserve/shared-types").InventoryStockLevelsResponse>(
    `/reports/cafeteria/${cafeteriaId}/inventory/stock-levels`,
  );
}

/** Items currently low or out of stock for one cafeteria (no date range). */
export async function getInventoryLowStockReport(
  cafeteriaId: string,
): Promise<import("@uniserve/shared-types").InventoryLowStockResponse> {
  return apiClient.get<import("@uniserve/shared-types").InventoryLowStockResponse>(
    `/reports/cafeteria/${cafeteriaId}/inventory/low-stock`,
  );
}

/** Inventory adjustment activity — restock vs usage over a date range. */
export async function getInventoryTurnoverReport(
  cafeteriaId: string,
  params?: { start_date?: string; end_date?: string },
): Promise<import("@uniserve/shared-types").InventoryTurnoverResponse> {
  return apiClient.get<import("@uniserve/shared-types").InventoryTurnoverResponse>(
    `/reports/cafeteria/${cafeteriaId}/inventory/turnover${reportQuery(params)}`,
  );
}

/** Peak-hour order volume by hour of day (created_at) for one cafeteria. */
export async function getCafeteriaPeakHoursReport(
  cafeteriaId: string,
  params?: { start_date?: string; end_date?: string },
): Promise<import("@uniserve/shared-types").CafeteriaPeakHoursResponse> {
  return apiClient.get<import("@uniserve/shared-types").CafeteriaPeakHoursResponse>(
    `/reports/cafeteria/${cafeteriaId}/peak-hours${reportQuery(params)}`,
  );
}

// Refunds (Admin) — Phase 51: enriched admin list/detail + rejection workflow
export async function getAllRefunds(params?: {
  cafeteria_id?: string;
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<import("@uniserve/shared-types").RefundAdminListResponse> {
  const query = new URLSearchParams();
  if (params?.cafeteria_id) query.set("cafeteria_id", params.cafeteria_id);
  if (params?.status) query.set("status", params.status);
  if (params?.limit) query.set("limit", String(params.limit));
  if (params?.offset) query.set("offset", String(params.offset));
  const qs = query.toString();
  return apiClient.get<import("@uniserve/shared-types").RefundAdminListResponse>(
    `/refunds/admin/all${qs ? `?${qs}` : ""}`,
  );
}

/** Phase 51 — enriched admin detail (student/order/payment context). */
export async function getAdminRefund(
  refundId: string,
): Promise<import("@uniserve/shared-types").RefundAdminResponse> {
  return apiClient.get<import("@uniserve/shared-types").RefundAdminResponse>(
    `/refunds/admin/${refundId}`,
  );
}

export async function processRefund(refundId: string) {
  return apiClient.post<any>(`/refunds/${refundId}/process`);
}

/**
 * Phase 51 — reject a pending refund with a persisted admin reason.
 * Rejection records the decision; it performs no money movement.
 */
export async function rejectRefund(
  refundId: string,
  data: import("@uniserve/shared-types").RefundRejectRequest,
): Promise<import("@uniserve/shared-types").RefundAdminResponse> {
  return apiClient.post<import("@uniserve/shared-types").RefundAdminResponse>(
    `/refunds/${refundId}/reject`,
    data,
  );
}

// Notifications
export async function markNotificationRead(notificationId: string) {
  return apiClient.patch<any>(`/notifications/${notificationId}/read`);
}

export async function markAllNotificationsRead() {
  return apiClient.patch<any>("/notifications/read-all");
}

// Phase 50 — Admin broadcast (University Admin only; backend RBAC enforced)
export async function broadcastNotification(
  data: import("@uniserve/shared-types").BroadcastCreateRequest,
): Promise<import("@uniserve/shared-types").BroadcastResponse> {
  return apiClient.post<import("@uniserve/shared-types").BroadcastResponse>(
    "/notifications/broadcast",
    data,
  );
}

export async function getBroadcastAudienceCount(params: {
  audience: import("@uniserve/shared-types").BroadcastAudience;
  cafeteria_id?: string;
}): Promise<import("@uniserve/shared-types").BroadcastAudienceCountResponse> {
  const query = new URLSearchParams();
  query.set("audience", params.audience);
  if (params.cafeteria_id) query.set("cafeteria_id", params.cafeteria_id);
  return apiClient.get<import("@uniserve/shared-types").BroadcastAudienceCountResponse>(
    `/notifications/broadcasts/audience-count?${query.toString()}`,
  );
}

export async function getAdminBroadcasts(params?: {
  limit?: number;
  offset?: number;
}): Promise<import("@uniserve/shared-types").BroadcastListResponse> {
  const query = new URLSearchParams();
  if (params?.limit) query.set("limit", String(params.limit));
  if (params?.offset) query.set("offset", String(params.offset));
  const qs = query.toString();
  return apiClient.get<import("@uniserve/shared-types").BroadcastListResponse>(
    `/notifications/broadcasts${qs ? `?${qs}` : ""}`,
  );
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

// ---- Menu item images (Phase 48) ----
// Raw-binary upload: the backend endpoint expects image bytes with an
// image/* Content-Type (no multipart — python-multipart is not shipped).

/** 48B — upload/replace a menu item's image; returns the updated MenuItem. */
export async function uploadMenuItemImage(
  cafeteriaId: string,
  menuItemId: string,
  file: File,
): Promise<import("@uniserve/shared-types").MenuItem> {
  return apiClient.uploadBinary<
    import("@uniserve/shared-types").MenuItem
  >(
    "POST",
    `/cafeterias/${cafeteriaId}/menu-items/${menuItemId}/image`,
    file,
    file.type || "application/octet-stream",
  );
}

/** 48B — remove a menu item's image; the item stays fully usable. */
export async function removeMenuItemImage(
  cafeteriaId: string,
  menuItemId: string,
): Promise<import("@uniserve/shared-types").MenuItem> {
  return apiClient.delete<import("@uniserve/shared-types").MenuItem>(
    `/cafeterias/${cafeteriaId}/menu-items/${menuItemId}/image`,
  );
}

// ---------------------------------------------------------------------------
// API error transparency (Phase 46)
// ---------------------------------------------------------------------------
// The shared ApiClient (packages/shared-types) throws structured
// ApiClientError values for every failure. These helpers turn any thrown
// value into a safe, user-facing description so pages can render an explicit
// error state (components/ui/LoadErrorState) instead of silently presenting a
// failed request as an empty dataset.
//
// Status conventions preserved from ApiClientError:
//   401 session expired (after a failed refresh)  -> auth
//   403 permission denied (RBAC / assignment)     -> permission
//   408 request timeout                           -> timeout
//   0   network failure (fetch rejected)          -> network
//   5xx backend error                             -> server (generic message)
//   4xx other backend rejection (validation,
//         not-found, conflict, ...)               -> client (backend detail)

export type ApiErrorKind =
  | "auth"
  | "permission"
  | "network"
  | "timeout"
  | "server"
  | "client"
  | "unknown";

export interface ApiErrorInfo {
  kind: ApiErrorKind;
  /** Safe, user-facing message. Never contains backend internals. */
  message: string;
  /** Original HTTP status (0 = network failure, -1 = unknown). */
  status: number;
  /** True when re-running the same request is meaningful. */
  retryable: boolean;
}

export function getApiErrorInfo(err: unknown): ApiErrorInfo {
  if (err instanceof ApiClientError) {
    if (err.status === 401) {
      return {
        kind: "auth",
        message: "Your session has expired. Please log in again.",
        status: 401,
        retryable: true,
      };
    }
    if (err.status === 403) {
      return {
        kind: "permission",
        message:
          err.message || "You do not have permission to access this data.",
        status: 403,
        retryable: false,
      };
    }
    if (err.status === 408) {
      return {
        kind: "timeout",
        message: "The request timed out. Please try again.",
        status: 408,
        retryable: true,
      };
    }
    if (err.status === 0) {
      return {
        kind: "network",
        message:
          "Unable to reach the server. Check your connection and try again.",
        status: 0,
        retryable: true,
      };
    }
    if (err.status >= 500) {
      // Generic on purpose — backend error bodies are not rendered to users.
      return {
        kind: "server",
        message: "The server encountered a problem. Please try again.",
        status: err.status,
        retryable: true,
      };
    }
    // Remaining 4xx: the backend detail is a safe, actionable message
    // (validation errors, not-found, conflict, ...).
    return {
      kind: "client",
      message: err.message || "The request could not be completed.",
      status: err.status,
      retryable: false,
    };
  }
  return {
    kind: "unknown",
    message: "Something went wrong. Please try again.",
    status: -1,
    retryable: true,
  };
}
