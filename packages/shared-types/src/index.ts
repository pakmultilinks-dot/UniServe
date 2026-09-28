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

export type OperationalStatus = "open" | "closed" | "closing_soon" | "maintenance";

export type MenuCategory =
  | "breakfast"
  | "main_course"
  | "side_dish"
  | "dessert"
  | "beverage"
  | "snack"
  | "salad"
  | "soup";

export type DailyMenuStatus = "draft" | "published" | "archived";

export type InventoryUnit = "kg" | "g" | "L" | "mL" | "pcs" | "portions";

export type CartStatus = "active" | "expired";

export type OrderStatus =
  | "pending"
  | "preparing"
  | "ready"
  | "completed"
  | "cancelled";

export type OrderType = "immediate" | "scheduled";

export type PaymentStatus =
  | "pending"
  | "processing"
  | "succeeded"
  | "failed"
  | "cancelled"
  | "refund_pending"
  | "partially_refunded"
  | "refunded";

export type PaymentMethod = "cash" | "online";

export type RefundStatus = "pending" | "processing" | "succeeded" | "failed";

export type RefundReason =
  | "order_cancelled"
  | "item_unavailable"
  | "payment_error"
  | "duplicate_payment"
  | "cafeteria_closed"
  | "other";

export type DeliveryStatus = "pending" | "delivered" | "failed";

export type NotificationType =
  | "order_created"
  | "order_confirmed"
  | "order_rejected"
  | "preparation_started"
  | "order_ready"
  | "order_cancelled"
  | "order_delayed"
  | "order_uncollected"
  | "cafeteria_closed"
  | "payment_confirmed"
  | "refund_requested"
  | "refund_processed"
  | "refund_failed";

export type OrderEventType =
  | "created"
  | "payment_pending"
  | "payment_confirmed"
  | "confirmed_by_staff"
  | "manager_rejected"
  | "preparation_started"
  | "ready_for_collection"
  | "collected"
  | "cancelled"
  | "cancelled_by_manager"
  | "inventory_reserved"
  | "inventory_released"
  | "uncollected"
  | "delayed"
  | "eta_updated"
  | "cafeteria_closed"
  | "item_unavailable"
  | "partial_cancelled"
  | "no_show_recorded";

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
  created_at: string;
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
  university_email: string;
  otp: string;
  new_password: string;
}

export interface PasswordChangeRequest {
  current_password: string;
  new_password: string;
}

export interface Session {
  id: string;
  device_info?: string;
  ip_address?: string;
  created_at: string;
  last_activity_at: string;
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
  type: CafeteriaType;
  description?: string;
  phone?: string;
  email?: string;
  location?: string;
  operating_hours?: string;
  timezone: string;
  operational_status: OperationalStatus;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CafeteriaCreate {
  name: string;
  type: CafeteriaType;
  description?: string;
  phone?: string;
  email?: string;
  location?: string;
  operating_hours?: string;
  timezone?: string;
}

export interface CafeteriaUpdate {
  name?: string;
  description?: string;
  phone?: string;
  email?: string;
  location?: string;
  operating_hours?: string;
  timezone?: string;
  is_active?: boolean;
}

// ═══════════════════════════════════════════════════════════════════
// MENU
// ═══════════════════════════════════════════════════════════════════

export interface MenuItem {
  id: string;
  cafeteria_id: string;
  name: string;
  description?: string;
  category: MenuCategory;
  price: number;
  currency: string;
  image_url?: string;
  dietary_info?: string;
  allergens?: string;
  preparation_time_minutes?: number;
  is_available: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface MenuItemCreate {
  name: string;
  description?: string;
  category: MenuCategory;
  price: number;
  currency?: string;
  image_url?: string;
  dietary_info?: string;
  allergens?: string;
}

export interface MenuItemUpdate {
  name?: string;
  description?: string;
  category?: MenuCategory;
  price?: number;
  currency?: string;
  image_url?: string;
  dietary_info?: string;
  allergens?: string;
  is_available?: boolean;
  is_active?: boolean;
}

export interface DailyMenu {
  id: string;
  cafeteria_id: string;
  menu_date: string;
  status: DailyMenuStatus;
  published_at?: string;
  created_by?: string;
  created_at: string;
  updated_at: string;
  items: DailyMenuItem[];
}

export interface DailyMenuCreate {
  menu_date: string;
}

export interface DailyMenuItem {
  id: string;
  menu_item_id: string;
  special_price?: number;
  is_available_today: boolean;
  display_order: number;
  notes?: string;
  menu_item?: MenuItem;
}

// ═══════════════════════════════════════════════════════════════════
// FAVORITES
// ═══════════════════════════════════════════════════════════════════

export interface Favorite {
  id: string;
  menu_item_id: string;
  created_at: string;
}

export interface FavoriteResponse {
  id: string;
  menu_item_id: string;
  menu_item?: MenuItem;
  created_at: string;
}

// ═══════════════════════════════════════════════════════════════════
// INVENTORY
// ═══════════════════════════════════════════════════════════════════

export interface InventoryItem {
  id: string;
  cafeteria_id: string;
  menu_item_id: string;
  quantity: number;
  unit: InventoryUnit;
  low_threshold: number;
  is_low: boolean;
  last_restocked_at?: string;
  created_at: string;
  updated_at: string;
}

export interface InventoryCreate {
  menu_item_id: string;
  quantity?: number;
  unit: InventoryUnit;
  low_threshold?: number;
}

export interface InventoryUpdate {
  quantity?: number;
  unit?: InventoryUnit;
  low_threshold?: number;
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
  status: CartStatus;
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
  item_name: string;
  unit_price: number;
  quantity: number;
  subtotal: number;
  currency: string;
}

export interface Order {
  id: string;
  order_number: number;
  user_id: string;
  cafeteria_id: string;
  status: OrderStatus;
  order_type: OrderType;
  payment_method: PaymentMethod;
  total_amount: number;
  currency: string;
  order_date: string;
  scheduled_collection_time?: string;
  items: OrderItem[];
  note?: string;
  inventory_reserved: boolean;
  confirmed_at?: string;
  preparation_started_at?: string;
  ready_at?: string;
  pickup_deadline?: string;
  eta_minutes?: number;
  collection_method?: string;
  rejection_reason?: string;
  rejection_note?: string;
  collected_at?: string;
  cancelled_at?: string;
  cancellation_reason?: string;
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
  amount: number;
  currency: string;
  status: PaymentStatus;
  provider_name?: string;
  created_at: string;
  updated_at: string;
}

export interface PaymentCreate {
  order_id: string;
  idempotency_key: string;
}

// ═══════════════════════════════════════════════════════════════════
// REFUNDS
// ═══════════════════════════════════════════════════════════════════

export interface Refund {
  id: string;
  order_id: string;
  payment_id: string;
  amount: number;
  currency: string;
  status: RefundStatus;
  reason: RefundReason;
  reason_note?: string;
  requested_by: string;
  processed_by?: string;
  provider_reference?: string;
  created_at: string;
  processed_at?: string;
  updated_at: string;
}

export interface RefundRequest {
  amount: number;
  reason: RefundReason;
  reason_note?: string;
  idempotency_key: string;
}

// ═══════════════════════════════════════════════════════════════════
// NOTIFICATIONS
// ═══════════════════════════════════════════════════════════════════

export interface Notification {
  id: string;
  notification_type: NotificationType;
  title: string;
  body: string;
  order_id?: string;
  cafeteria_id?: string;
  reference_type?: string;
  reference_id?: string;
  is_read: boolean;
  delivery_status: DeliveryStatus;
  created_at: string;
  read_at?: string;
}

export interface NotificationListResponse {
  items: Notification[];
  total: number;
  unread_count: number;
}

export interface UnreadCountResponse {
  unread_count: number;
}

export interface MarkReadResponse {
  id: string;
  is_read: boolean;
  read_at: string;
}

export interface MarkAllReadResponse {
  marked_count: number;
}

// ═══════════════════════════════════════════════════════════════════
// REPORTS
// ═══════════════════════════════════════════════════════════════════

export type ReportType =
  | "daily_sales"
  | "revenue"
  | "popular_items"
  | "cafeteria_performance"
  | "user_activity"
  | "payment_summary";

export type ExportFormat = "csv" | "pdf";

// ---- Sales Reports ----

export interface SalesSummary {
  total_revenue: number;
  total_orders: number;
  total_refunded: number;
  net_revenue: number;
  currency: string;
}

export interface SalesReportResponse {
  summary: SalesSummary;
  currency: string;
}

export interface DailySalesRow {
  date: string;
  revenue: number;
  order_count: number;
}

export interface SalesDailyResponse {
  rows: DailySalesRow[];
  currency: string;
}

export interface CafeteriaSalesRow {
  cafeteria_id: string;
  cafeteria_name: string;
  revenue: number;
  order_count: number;
  refunded_amount: number;
}

export interface SalesByCafeteriaResponse {
  rows: CafeteriaSalesRow[];
  currency: string;
}

// ---- Order Analytics ----

export interface OrderStatusBreakdown {
  pending: number;
  preparing: number;
  ready: number;
  completed: number;
  cancelled: number;
}

export interface OrderTypeBreakdown {
  immediate: number;
  scheduled: number;
}

export interface OrderPaymentBreakdown {
  cash: number;
  online: number;
}

export interface OrderSummaryResponse {
  total_orders: number;
  status_breakdown: OrderStatusBreakdown;
  type_breakdown: OrderTypeBreakdown;
  payment_breakdown: OrderPaymentBreakdown;
  cancellation_rate: number;
  completion_rate: number;
}

export interface DailyVolumeRow {
  date: string;
  order_count: number;
  completed_count: number;
  cancelled_count: number;
}

export interface HourlyVolumeRow {
  hour: number;
  order_count: number;
}

export interface OrderVolumeResponse {
  daily: DailyVolumeRow[];
  hourly: HourlyVolumeRow[];
}

export interface CancellationRateResponse {
  total_orders: number;
  cancelled_orders: number;
  cancellation_rate: number;
  cancellation_reasons: Record<string, number>;
}

// ---- Cafeteria Performance ----

export interface CafeteriaPerformanceResponse {
  cafeteria_id: string;
  cafeteria_name: string;
  total_orders: number;
  completed_orders: number;
  cancelled_orders: number;
  uncollected_orders: number;
  completion_rate: number;
  cancellation_rate: number;
  avg_preparation_time_minutes: number | null;
  avg_time_to_ready_minutes: number | null;
  avg_eta_minutes: number | null;
}

export interface PopularItemRow {
  menu_item_id: string | null;
  item_name: string;
  total_quantity: number;
  total_revenue: number;
  order_count: number;
}

export interface CafeteriaPopularItemsResponse {
  cafeteria_id: string;
  items: PopularItemRow[];
}

export interface PeakHourRow {
  hour: number;
  order_count: number;
  completed_count: number;
}

export interface CafeteriaPeakHoursResponse {
  cafeteria_id: string;
  timezone: string;
  hours: PeakHourRow[];
}

// ---- Inventory Reports ----

export interface InventoryStockLevelRow {
  inventory_item_id: string;
  menu_item_id: string;
  menu_item_name: string;
  quantity: number;
  unit: string;
  low_threshold: number;
  is_out_of_stock: boolean;
  is_low_stock: boolean;
}

export interface InventoryStockLevelsResponse {
  cafeteria_id: string;
  total_items: number;
  out_of_stock_count: number;
  low_stock_count: number;
  items: InventoryStockLevelRow[];
}

export interface InventoryLowStockRow {
  inventory_item_id: string;
  menu_item_id: string;
  menu_item_name: string;
  quantity: number;
  unit: string;
  low_threshold: number;
  stock_status: string;
}

export interface InventoryLowStockResponse {
  cafeteria_id: string;
  total_low_stock: number;
  items: InventoryLowStockRow[];
}

export interface InventoryAdjustmentRow {
  id: string;
  inventory_item_id: string;
  menu_item_name: string;
  adjustment_quantity: number;
  reason: string | null;
  adjusted_at: string;
}

export interface InventoryTurnoverResponse {
  cafeteria_id: string;
  total_adjustments: number;
  total_restock: number;
  total_usage: number;
  adjustments: InventoryAdjustmentRow[];
}

// ═══════════════════════════════════════════════════════════════════
// ADMINISTRATION (university_admin operations)
// ═══════════════════════════════════════════════════════════════════

export interface AdministrationUserSummary {
  total: number;
  students: number;
  faculty: number;
  university_admins: number;
  cafeteria_managers: number;
  cafeteria_staff: number;
  active: number;
  suspended: number;
  ordering_suspended: number;
}

export interface CafeteriaOverviewItem {
  cafeteria_id: string;
  name: string;
  type: string;
  operational_status: string;
  is_active: boolean;
  assigned_managers: number;
  assigned_staff: number;
  preparation_capacity: number;
}

export interface AdministrationCafeteriaSummary {
  total: number;
  active: number;
  cafeterias: CafeteriaOverviewItem[];
}

export interface AdministrationOrderSummary {
  total_orders: number;
  pending: number;
  preparing: number;
  ready: number;
  completed: number;
  cancelled: number;
  uncollected: number;
  cancellation_rate: number;
}

export interface AdministrationFinancialSummary {
  total_revenue: number;
  total_refunded: number;
  net_revenue: number;
  online_payment_volume: number;
  cash_payment_volume: number;
  currency: string;
}

export interface AdministrationExceptionsSummary {
  overdue_refunds: number;
  ordering_suspended_users: number;
  uncollected_orders: number;
  cafeteria_closure_cancellations: number;
}

export interface AdministrationOverviewResponse {
  users: AdministrationUserSummary;
  cafeterias: AdministrationCafeteriaSummary;
  orders: AdministrationOrderSummary;
  financial: AdministrationFinancialSummary;
  exceptions: AdministrationExceptionsSummary;
}

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

// ---- Additional Phase 6 types ----

export interface EtaResponse {
  order_id: string;
  eta_minutes: number;
  pickup_deadline: string | null;
}

export interface NoShowResponse {
  id: string;
  user_id: string;
  order_id: string;
  cafeteria_id: string;
  created_at: string;
}

export interface PaymentInitiationResponse {
  payment_id: string;
  status: string;
  provider_name?: string;
  redirect_url?: string;
  message: string;
}

export interface RefundableAmountResponse {
  order_id: string;
  paid_amount: number;
  total_refunded: number;
  refundable_amount: number;
  currency: string;
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

      // Attempt token refresh on 401 when a refresh token is available.
      // This covers both expired-access-token (token was sent) and
      // absent-access-token (e.g. page reload) scenarios.
      if (response.status === 401 && this.tokenProvider.getRefreshToken()) {
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
