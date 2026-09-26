/**
 * UniServe — Shared Type Definitions & API Client
 *
 * Types shared across mobile, web, and API applications.
 * Derived from the backend Pydantic schemas (authoritative source).
 *
 * IMPORTANT: The backend is the authoritative source for business rules.
 * This file mirrors the backend's public contract for frontend consumption.
 */

// ═══════════════════════════════════════════════════════════════════
// ENUMS & LITERAL TYPES
// ═══════════════════════════════════════════════════════════════════

export type UserRole =
  | "student"
  | "faculty"
  | "cafeteria_staff"
  | "cafeteria_manager"
  | "university_admin";

export type UserCategory = "student" | "faculty";

export type AccountStatus =
  | "pending_verification"
  | "active"
  | "suspended"
  | "deleted";

export type OTPPurpose = "email_verification" | "password_reset";

export type CafeteriaType = "student" | "faculty";

export type OrderStatus =
  | "pending"
  | "confirmed"
  | "preparing"
  | "ready_for_pickup"
  | "completed"
  | "cancelled"
  | "no_show";

export type OrderType = "immediate" | "scheduled";

export type PaymentStatus =
  | "pending"
  | "completed"
  | "failed"
  | "refunded"
  | "partially_refunded";

export type PaymentMethod = "cash" | "online";

export type RefundStatus = "pending" | "approved" | "rejected" | "completed";

export type CartItemStatus = "active" | "checked_out" | "expired";

export type NotificationType =
  | "order_update"
  | "payment_update"
  | "promotion"
  | "system"
  | "admin_alert";

export type ReportType =
  | "daily_sales"
  | "revenue"
  | "popular_items"
  | "cafeteria_performance"
  | "user_activity"
  | "payment_summary";

export type ExportFormat = "csv" | "pdf";

export type SortOrder = "asc" | "desc";

// ═══════════════════════════════════════════════════════════════════
// USER & AUTHENTICATION
// ═══════════════════════════════════════════════════════════════════

export interface User {
  id: string;
  first_name: string;
  last_name: string;
  university_id: string;
  university_email: string;
  category: UserCategory;
  role: UserRole;
  status: AccountStatus;
  email_verified: boolean;
  pin_set: boolean;
  created_at: string;
  updated_at: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  expires_in: number;
}

export interface LoginRequest {
  university_email: string;
  password: string;
}

export interface LoginResponse {
  tokens: TokenPair;
  user: User;
}

export interface RegisterRequest {
  first_name: string;
  last_name: string;
  university_id: string;
  university_email: string;
  password: string;
}

export interface RegisterResponse {
  message: string;
  user_id: string;
  university_email: string;
  category: UserCategory;
}

export interface OTPVerifyRequest {
  user_id: string;
  otp: string;
  purpose: OTPPurpose;
}

export interface OTPResendRequest {
  user_id: string;
  purpose: OTPPurpose;
}

export interface OTPResponse {
  message: string;
  expires_in_seconds?: number;
}

export interface PINLoginRequest {
  user_id: string;
  pin: string;
}

export interface PINSetRequest {
  pin: string;
}

export interface PINChangeRequest {
  current_pin: string;
  new_pin: string;
}

export interface RefreshTokenRequest {
  refresh_token: string;
}

export interface PasswordResetRequest {
  university_email: string;
}

export interface PasswordResetConfirm {
  user_id: string;
  otp: string;
  new_password: string;
}

export interface PasswordChangeRequest {
  current_password: string;
  new_password: string;
}

export interface Session {
  id: string;
  user_id: string;
  device_info?: string;
  ip_address?: string;
  created_at: string;
  last_activity_at: string;
  expires_at: string;
  is_current: boolean;
}

export interface SessionListResponse {
  sessions: Session[];
}

export interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  isEmailVerified: boolean;
}

// ═══════════════════════════════════════════════════════════════════
// CAFETERIA
// ═══════════════════════════════════════════════════════════════════

export interface Cafeteria {
  id: string;
  name: string;
  cafeteria_type: CafeteriaType;
  description?: string;
  location?: string;
  is_active: boolean;
  operating_hours?: string;
  created_at: string;
  updated_at: string;
}

export interface CafeteriaCreate {
  name: string;
  cafeteria_type: CafeteriaType;
  description?: string;
  location?: string;
  is_active?: boolean;
  operating_hours?: string;
}

export interface CafeteriaUpdate {
  name?: string;
  cafeteria_type?: CafeteriaType;
  description?: string;
  location?: string;
  is_active?: boolean;
  operating_hours?: string;
}

// ═══════════════════════════════════════════════════════════════════
// MENU
// ═══════════════════════════════════════════════════════════════════

export interface MenuItem {
  id: string;
  cafeteria_id: string;
  name: string;
  description?: string;
  price: number;
  currency: string;
  category?: string;
  is_available: boolean;
  image_url?: string;
  created_at: string;
  updated_at: string;
}

export interface MenuItemCreate {
  name: string;
  description?: string;
  price: number;
  currency?: string;
  category?: string;
  is_available?: boolean;
  image_url?: string;
}

export interface MenuItemUpdate {
  name?: string;
  description?: string;
  price?: number;
  currency?: string;
  category?: string;
  is_available?: boolean;
  image_url?: string;
}

export interface DailyMenu {
  id: string;
  cafeteria_id: string;
  date: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface DailyMenuCreate {
  date: string;
  is_active?: boolean;
  menu_item_ids?: string[];
}

export interface DailyMenuItem {
  id: string;
  daily_menu_id: string;
  menu_item_id: string;
  display_order: number;
  is_available: boolean;
}

// ═══════════════════════════════════════════════════════════════════
// FAVORITES
// ═══════════════════════════════════════════════════════════════════

export interface Favorite {
  id: string;
  user_id: string;
  menu_item_id: string;
  created_at: string;
}

export interface FavoriteResponse {
  id: string;
  menu_item_id: string;
  menu_item_name: string;
  cafeteria_id: string;
  cafeteria_name: string;
  price: number;
  currency: string;
  created_at: string;
}

// ═══════════════════════════════════════════════════════════════════
// INVENTORY
// ═══════════════════════════════════════════════════════════════════

export interface InventoryItem {
  id: string;
  cafeteria_id: string;
  menu_item_id: string;
  current_quantity: number;
  low_stock_threshold: number;
  unit: string;
  last_restocked_at?: string;
  created_at: string;
  updated_at: string;
}

export interface InventoryCreate {
  menu_item_id: string;
  current_quantity: number;
  low_stock_threshold?: number;
  unit?: string;
}

export interface InventoryUpdate {
  current_quantity?: number;
  low_stock_threshold?: number;
  unit?: string;
}

// ═══════════════════════════════════════════════════════════════════
// CART
// ═══════════════════════════════════════════════════════════════════

export interface CartItemResponse {
  id: string;
  menu_item_id: string;
  quantity: number;
  price_snapshot: number;
  currency: string;
  subtotal: number;
  item_name?: string;
  item_available?: boolean;
  created_at: string;
  updated_at: string;
}

export interface CartResponse {
  id: string;
  user_id: string;
  cafeteria_id: string;
  status: string;
  items: CartItemResponse[];
  total_amount: number;
  item_count: number;
  created_at: string;
  updated_at: string;
}

export interface CartAddItemRequest {
  menu_item_id: string;
  quantity: number;
}

export interface CartUpdateQuantityRequest {
  quantity: number;
}

export interface CartCheckoutRequest {
  payment_method?: PaymentMethod;
  order_type?: OrderType;
  scheduled_collection_time?: string;
  note?: string;
}

// ═══════════════════════════════════════════════════════════════════
// ORDERS
// ═══════════════════════════════════════════════════════════════════

export interface OrderItem {
  id: string;
  order_id: string;
  menu_item_id: string;
  menu_item_name: string;
  quantity: number;
  unit_price: number;
  subtotal: number;
  currency: string;
}

export interface Order {
  id: string;
  user_id: string;
  cafeteria_id: string;
  cafeteria_name: string;
  status: OrderStatus;
  order_type: OrderType;
  total_amount: number;
  currency: string;
  payment_method: PaymentMethod;
  payment_status: PaymentStatus;
  note?: string;
  scheduled_collection_time?: string;
  pickup_code?: string;
  items: OrderItem[];
  created_at: string;
  updated_at: string;
}

export interface OrderCreate {
  cafeteria_id: string;
  items: { menu_item_id: string; quantity: number }[];
  order_type?: OrderType;
  payment_method?: PaymentMethod;
  note?: string;
  scheduled_collection_time?: string;
}

export interface OrderUpdateStatus {
  status: OrderStatus;
  note?: string;
}

// ═══════════════════════════════════════════════════════════════════
// PAYMENTS
// ═══════════════════════════════════════════════════════════════════

export interface Payment {
  id: string;
  order_id: string;
  user_id: string;
  amount: number;
  currency: string;
  method: PaymentMethod;
  status: PaymentStatus;
  transaction_id?: string;
  created_at: string;
  updated_at: string;
}

export interface PaymentCreate {
  order_id: string;
  method: PaymentMethod;
}

// ═══════════════════════════════════════════════════════════════════
// REFUNDS
// ═══════════════════════════════════════════════════════════════════

export interface Refund {
  id: string;
  payment_id: string;
  order_id: string;
  user_id: string;
  amount: number;
  currency: string;
  reason: string;
  status: RefundStatus;
  processed_by?: string;
  processed_at?: string;
  created_at: string;
  updated_at: string;
}

export interface RefundRequest {
  reason: string;
}

// ═══════════════════════════════════════════════════════════════════
// NOTIFICATIONS
// ═══════════════════════════════════════════════════════════════════

export interface Notification {
  id: string;
  user_id: string;
  title: string;
  message: string;
  notification_type: NotificationType;
  is_read: boolean;
  data?: Record<string, unknown>;
  created_at: string;
}

// ═══════════════════════════════════════════════════════════════════
// REPORTS
// ═══════════════════════════════════════════════════════════════════

export interface ReportRequest {
  report_type: ReportType;
  cafeteria_id?: string;
  start_date: string;
  end_date: string;
  format?: ExportFormat;
}

export interface DailySalesReport {
  date: string;
  cafeteria_id: string;
  cafeteria_name: string;
  total_orders: number;
  total_revenue: number;
  currency: string;
  average_order_value: number;
  items_sold: { menu_item_id: string; name: string; quantity: number; revenue: number }[];
}

export interface RevenueReport {
  period_start: string;
  period_end: string;
  cafeteria_id?: string;
  total_revenue: number;
  currency: string;
  total_orders: number;
  revenue_by_cafeteria: { cafeteria_id: string; cafeteria_name: string; revenue: number }[];
  revenue_by_day: { date: string; revenue: number }[];
}

export interface PopularItemsReport {
  period_start: string;
  period_end: string;
  cafeteria_id?: string;
  items: {
    menu_item_id: string;
    name: string;
    cafeteria_name: string;
    total_quantity: number;
    total_revenue: number;
  }[];
}

export interface CafeteriaPerformanceReport {
  period_start: string;
  period_end: string;
  cafeterias: {
    cafeteria_id: string;
    name: string;
    total_orders: number;
    total_revenue: number;
    average_order_value: number;
    completion_rate: number;
    cancellation_rate: number;
  }[];
}

export interface UserActivityReport {
  period_start: string;
  period_end: string;
  total_users: number;
  active_users: number;
  new_registrations: number;
  users_by_role: { role: UserRole; count: number }[];
  users_by_category: { category: UserCategory; count: number }[];
}

export interface PaymentSummaryReport {
  period_start: string;
  period_end: string;
  total_transactions: number;
  total_amount: number;
  currency: string;
  by_method: { method: PaymentMethod; count: number; amount: number }[];
  by_status: { status: PaymentStatus; count: number; amount: number }[];
}

// ═══════════════════════════════════════════════════════════════════
// ADMINISTRATION (university_admin operations)
// ═══════════════════════════════════════════════════════════════════

export interface AdminUserUpdate {
  role?: UserRole;
  status?: AccountStatus;
}

export interface AdminCafeteriaStaffCreate {
  university_email: string;
  first_name: string;
  last_name: string;
  university_id: string;
  category: UserCategory;
  cafeteria_id: string;
}

export interface CafeteriaAssignment {
  id: string;
  user_id: string;
  cafeteria_id: string;
  assigned_at: string;
}

// ═══════════════════════════════════════════════════════════════════
// API RESPONSE COMMON
// ═══════════════════════════════════════════════════════════════════

export interface ApiResponse<T> {
  data: T;
  message?: string;
}

export interface ApiErrorResponse {
  detail: string;
  code?: string;
  status_code?: number;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

export interface PaginatedQuery {
  page?: number;
  pageSize?: number;
  search?: string;
  sortBy?: string;
  sortOrder?: SortOrder;
}

// ═══════════════════════════════════════════════════════════════════
// API CLIENT
//
// Generic, typed HTTP client with auth-header injection, timeout,
// automatic token refresh on 401, and consistent error handling.
// Platform-agnostic — each app provides its own TokenProvider.
// ═══════════════════════════════════════════════════════════════════

/**
 * Platform-specific token storage contract.
 * Web: in-memory + sessionStorage. Mobile: SecureStore.
 */
export interface TokenProvider {
  getAccessToken(): string | null;
  getRefreshToken(): string | null;
  setTokens(accessToken: string, refreshToken: string): void;
  clearTokens(): void;
}

/**
 * Typed API error with HTTP status and optional error code.
 */
export class ApiClientError extends Error {
  constructor(
    public status: number,
    message: string,
    public code?: string,
  ) {
    super(message);
    this.name = "ApiClientError";
  }
}

/**
 * Typed HTTP client with automatic auth header injection,
 * request timeout, token refresh on 401, and typed responses.
 */
export class ApiClient {
  private baseUrl: string;
  private tokenProvider: TokenProvider;
  private refreshPromise: Promise<string | null> | null = null;
  private onAuthFailure?: () => void;

  constructor(
    baseUrl: string,
    tokenProvider: TokenProvider,
    onAuthFailure?: () => void,
  ) {
    this.baseUrl = baseUrl;
    this.tokenProvider = tokenProvider;
    this.onAuthFailure = onAuthFailure;
  }

  async request<T>(
    method: string,
    endpoint: string,
    options?: { body?: unknown; timeout?: number },
  ): Promise<T> {
    const { body, timeout = 15000 } = options ?? {};
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    try {
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };

      const token = this.tokenProvider.getAccessToken();
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      let response = await fetch(`${this.baseUrl}${endpoint}`, {
        method,
        headers,
        body: body != null ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });

      // Attempt token refresh on 401 (only if we had a token)
      if (response.status === 401 && token) {
        const newToken = await this.handleTokenRefresh();
        if (newToken) {
          headers["Authorization"] = `Bearer ${newToken}`;
          response = await fetch(`${this.baseUrl}${endpoint}`, {
            method,
            headers,
            body: body != null ? JSON.stringify(body) : undefined,
            signal: controller.signal,
          });
        } else {
          // Refresh failed — clear auth and notify
          this.tokenProvider.clearTokens();
          this.onAuthFailure?.();
          throw new ApiClientError(401, "Session expired. Please log in again.");
        }
      }

      return await this.handleResponse<T>(response);
    } catch (err) {
      if (err instanceof ApiClientError) throw err;
      if (err instanceof DOMException && err.name === "AbortError") {
        throw new ApiClientError(408, "Request timed out");
      }
      throw new ApiClientError(0, `Network error: ${(err as Error).message ?? "unknown"}`);
    } finally {
      clearTimeout(timeoutId);
    }
  }

  // ---- HTTP verb shortcuts ----

  get<T>(endpoint: string): Promise<T> {
    return this.request<T>("GET", endpoint);
  }

  post<T>(endpoint: string, body?: unknown): Promise<T> {
    return this.request<T>("POST", endpoint, { body });
  }

  put<T>(endpoint: string, body?: unknown): Promise<T> {
    return this.request<T>("PUT", endpoint, { body });
  }

  patch<T>(endpoint: string, body?: unknown): Promise<T> {
    return this.request<T>("PATCH", endpoint, { body });
  }

  delete<T>(endpoint: string): Promise<T> {
    return this.request<T>("DELETE", endpoint);
  }

  // ---- Internal helpers ----

  private async handleResponse<T>(response: Response): Promise<T> {
    if (response.status === 204) return undefined as T;

    const data = await response.json().catch(() => null);

    if (!response.ok) {
      const detail =
        (data as Record<string, unknown>)?.detail as string | undefined;
      const code =
        (data as Record<string, unknown>)?.code as string | undefined;
      throw new ApiClientError(
        response.status,
        detail ?? `API error: ${response.status}`,
        code,
      );
    }

    return data as T;
  }

  /**
   * Deduplicates concurrent refresh requests.
   */
  private async handleTokenRefresh(): Promise<string | null> {
    const refreshToken = this.tokenProvider.getRefreshToken();
    if (!refreshToken) return null;

    if (this.refreshPromise) return this.refreshPromise;

    this.refreshPromise = (async () => {
      try {
        const response = await fetch(`${this.baseUrl}/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });

        if (!response.ok) return null;

        const data = (await response.json()) as TokenPair;
        this.tokenProvider.setTokens(data.access_token, data.refresh_token);
        return data.access_token;
      } catch {
        return null;
      } finally {
        this.refreshPromise = null;
      }
    })();

    return this.refreshPromise;
  }
}
