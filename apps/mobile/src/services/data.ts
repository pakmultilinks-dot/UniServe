/**
 * UniServe — Data API Service (Mobile)
 *
 * API calls for cafeterias, menus, cart, orders, and notifications.
 * Uses the shared ApiClient with auth injection.
 * All types come from @uniserve/shared-types for consistency.
 */

import { apiClient } from "./api";
import type {
  Cafeteria,
  MenuItem,
  DailyMenu,
  CartResponse,
  CartItemResponse,
  CartAddItemRequest,
  CartUpdateQuantityRequest,
  CartCheckoutRequest,
  FavoriteResponse,
  MarkAllReadResponse,
  MarkReadResponse,
  Order,
  Payment,
  RefundReason,
} from "@uniserve/shared-types";

// ---- Cafeterias ----

interface CafeteriaListResponse {
  cafeterias: Cafeteria[];
  total: number;
}

/**
 * Fetch cafeterias for the mobile ordering path.
 *
 * Phase 58 (Workstream A) — customer roles explicitly request active-only
 * cafeterias (?is_active=true) so inactive cafeterias never enter
 * operational customer selection, even if the backend default changed.
 * For students, the backend additionally filters to student cafeterias.
 */
export async function getCafeterias(): Promise<Cafeteria[]> {
  const data = await apiClient.get<CafeteriaListResponse>("/cafeterias?is_active=true");
  return data.cafeterias ?? [];
}

// ---- Menu Items ----

/** Fetch a single menu item by ID. */
export async function getMenuItem(
  cafeteriaId: string,
  menuItemId: string,
): Promise<MenuItem> {
  return apiClient.get<MenuItem>(
    `/cafeterias/${cafeteriaId}/menu-items/${menuItemId}`,
  );
}

/** Fetch today's published daily menu for a cafeteria. Returns null if no menu is published. */
export async function getTodaysMenu(cafeteriaId: string): Promise<DailyMenu | null> {
  return apiClient.get<DailyMenu | null>(
    `/cafeterias/${cafeteriaId}/daily-menus/today`,
  );
}

// ---- Cart ----

/** Get the active cart for a cafeteria. */
export async function getCart(cafeteriaId: string): Promise<CartResponse> {
  return apiClient.get<CartResponse>(`/cafeterias/${cafeteriaId}/cart`);
}

/** Add an item to the cart. Returns the new cart item. */
export async function addCartItem(
  cafeteriaId: string,
  menuItemId: string,
  quantity: number,
): Promise<CartItemResponse> {
  const body: CartAddItemRequest = { menu_item_id: menuItemId, quantity };
  return apiClient.post<CartItemResponse>(`/cafeterias/${cafeteriaId}/cart/items`, body);
}

/** Update quantity of a cart item. Returns the updated cart item. */
export async function updateCartItemQuantity(
  cafeteriaId: string,
  cartItemId: string,
  quantity: number,
): Promise<CartItemResponse> {
  const body: CartUpdateQuantityRequest = { quantity };
  return apiClient.put<CartItemResponse>(
    `/cafeterias/${cafeteriaId}/cart/items/${cartItemId}`,
    body,
  );
}

/** Remove an item from the cart. */
export async function removeCartItem(
  cafeteriaId: string,
  cartItemId: string,
): Promise<void> {
  await apiClient.delete(`/cafeterias/${cafeteriaId}/cart/items/${cartItemId}`);
}

/** Checkout the cart and create an order. */
export async function checkoutCart(
  cafeteriaId: string,
  params: {
    payment_method?: "cash" | "online";
    order_type?: "immediate" | "scheduled";
    scheduled_collection_time?: string;
    note?: string;
    idempotency_key?: string;
  },
): Promise<Order> {
  const body: CartCheckoutRequest = {
    payment_method: params.payment_method ?? "cash",
    order_type: params.order_type ?? "immediate",
  };
  if (params.scheduled_collection_time) body.scheduled_collection_time = params.scheduled_collection_time;
  if (params.note) body.note = params.note;
  if (params.idempotency_key) body.idempotency_key = params.idempotency_key;
  return apiClient.post<Order>(`/cafeterias/${cafeteriaId}/cart/checkout`, body);
}

export async function initiatePayment(
  orderId: string,
  idempotencyKey: string,
): Promise<{ payment_id: string; status: string; provider_name?: string; redirect_url?: string; message: string }> {
  return apiClient.post(`/payments/initiate/${orderId}`, { idempotency_key: idempotencyKey });
}

export async function getOrderPayment(orderId: string): Promise<Payment> {
  return apiClient.get<Payment>(`/payments/order/${orderId}`);
}

// ---- Orders ----

interface OrderListResponse {
  orders: Order[];
  total: number;
}

export interface OrderParams {
  status?: string;
}

export async function getOrders(params?: OrderParams): Promise<Order[]> {
  // Backend GET /orders accepts only cafeteria_id/status/days — there is no
  // `limit` param (the default window is the last 7 days).
  const queryParams = new URLSearchParams();
  if (params?.status) queryParams.append("status", params.status);
  const qs = queryParams.toString();
  const data = await apiClient.get<OrderListResponse>(`/orders${qs ? `?${qs}` : ""}`);
  return data.orders ?? [];
}

/** Fetch a single order by ID. */
export async function getOrder(orderId: string): Promise<Order> {
  return apiClient.get<Order>(`/orders/${orderId}`);
}

/**
 * Cancel an order as the ordering user (P2 — Phase 40 acceptance).
 * Backend rules (unchanged): order must be PENDING, owned by the caller, and
 * for scheduled orders the 30-min-before-collection deadline is enforced
 * server-side using the cafeteria-local timezone.
 */
export async function cancelOrder(orderId: string, reason?: string): Promise<Order> {
  return apiClient.post<Order>(`/orders/${orderId}/cancel`, { reason });
}

// ---- Phase 58 — Customer self-service (Workstream B + E2) ----

/**
 * Cancel ONE item from a pending order (Workstream E2).
 * Backend: POST /orders/{id}/partial-cancel — OWNER-ONLY (a non-owner
 * receives "Order not found"); the order must be PENDING; removing the final
 * remaining item cancels the whole order; reserved inventory is released and
 * the order total is recalculated server-side. Returns the updated order.
 */
export async function partialCancelItem(
  orderId: string,
  itemId: string,
  reason?: string,
): Promise<Order> {
  return apiClient.post<Order>(`/orders/${orderId}/partial-cancel`, {
    item_id: itemId,
    reason: reason || null,
  });
}

/** Refundable-amount snapshot (GET /refunds/refundable/{order_id}). */
export interface RefundableAmount {
  order_id: string;
  paid_amount: number;
  total_refunded: number;
  refundable_amount: number;
  currency: string;
}

/** Refund record as returned by the OWNER-facing refund endpoints.
 * NOTE: the owner endpoint's response does NOT include the admin rejection
 * reason (that field exists only on the admin refund detail) — rejected
 * refunds are visible by status only. */
export interface OrderRefund {
  id: string;
  order_id: string;
  payment_id: string;
  amount: number;
  currency: string;
  status: string; // pending | processing | succeeded | failed | rejected
  reason: string;
  reason_note?: string | null;
  requested_by: string;
  processed_by?: string | null;
  provider_reference?: string | null;
  created_at: string;
  processed_at?: string | null;
  updated_at: string;
}

/**
 * Check the refundable amount for an order (Workstream B).
 * Backend: GET /refunds/refundable/{order_id} — OWNER-ONLY. Requires a
 * succeeded payment; all amounts are in paisa. The backend additionally
 * enforces the refund deadline (default 72h) when a refund is requested.
 */
export async function getRefundableAmount(orderId: string): Promise<RefundableAmount> {
  return apiClient.get<RefundableAmount>(`/refunds/refundable/${orderId}`);
}

/**
 * Submit a refund request (Workstream B).
 * Backend: POST /refunds?order_id=... — OWNER-ONLY; body
 * {amount (paisa, >0), reason (backend RefundReason enum), reason_note?
 * (≤500), idempotency_key (required)}. Idempotent: re-sending the same key
 * returns the existing refund. On success the refund is PENDING and must be
 * approved by an admin before the money is returned to the customer.
 */
export async function requestRefund(
  orderId: string,
  params: {
    amount: number;
    reason: RefundReason;
    reason_note?: string;
    idempotency_key: string;
  },
): Promise<OrderRefund> {
  return apiClient.post<OrderRefund>(
    `/refunds?order_id=${encodeURIComponent(orderId)}`,
    {
      amount: params.amount,
      reason: params.reason,
      reason_note: params.reason_note || null,
      idempotency_key: params.idempotency_key,
    },
  );
}

/** List an order's refunds (Workstream B). Backend: GET /refunds/order/{id}
 * — OWNER-ONLY. */
export async function getOrderRefunds(orderId: string): Promise<OrderRefund[]> {
  const data = await apiClient.get<{ refunds: OrderRefund[]; total: number }>(
    `/refunds/order/${orderId}`,
  );
  return data.refunds ?? [];
}

// ---- Notifications ----

export interface NotificationListResponse {
  items: Notification[];
  total: number;
  unread_count: number;
}

export interface Notification {
  id: string;
  title: string;
  body: string;
  notification_type: string;
  is_read: boolean;
  created_at: string;
  order_id?: string;
  cafeteria_id?: string;
  reference_type?: string;
  reference_id?: string;
  delivery_status?: string;
  read_at?: string;
}

export interface NotificationParams {
  unread_only?: boolean;
  limit?: number;
}

export async function getNotificationsPage(
  params?: NotificationParams,
): Promise<NotificationListResponse> {
  const queryParams = new URLSearchParams();
  if (params?.unread_only !== undefined) queryParams.append("unread_only", String(params.unread_only));
  if (params?.limit) queryParams.append("limit", String(params.limit));
  const qs = queryParams.toString();
  return apiClient.get<NotificationListResponse>(
    `/notifications${qs ? `?${qs}` : ""}`,
  );
}

export async function getUnreadNotificationCount(): Promise<number> {
  const response = await apiClient.get<{ unread_count: number }>("/notifications/unread-count");
  return response.unread_count;
}

/** Mark one of the current user's notifications as read (Phase 53).
 * The backend verifies ownership — a foreign notification id returns 404. */
export async function markNotificationRead(
  notificationId: string,
): Promise<MarkReadResponse> {
  return apiClient.patch<MarkReadResponse>(`/notifications/${notificationId}/read`);
}

/** Mark all of the current user's unread notifications as read (Phase 53).
 * Server-side UPDATE is scoped to auth.user.id — no cross-user writes. */
export async function markAllNotificationsRead(): Promise<MarkAllReadResponse> {
  return apiClient.patch<MarkAllReadResponse>("/notifications/read-all");
}

// ---- Favorites ----

interface FavoriteListResponse {
  favorites: FavoriteResponse[];
  total: number;
}

/** List the current user's favorite menu items (user-scoped server-side). */
export async function getFavorites(): Promise<FavoriteResponse[]> {
  const data = await apiClient.get<FavoriteListResponse>("/favorites");
  return data.favorites ?? [];
}

/** Add a menu item to the current user's favorites. */
export async function addFavorite(menuItemId: string): Promise<FavoriteResponse> {
  return apiClient.post<FavoriteResponse>("/favorites", { menu_item_id: menuItemId });
}

/** Remove a menu item from the current user's favorites. */
export async function removeFavorite(menuItemId: string): Promise<void> {
  await apiClient.delete<void>(`/favorites/${menuItemId}`);
}
