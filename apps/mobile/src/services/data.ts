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
  MenuCategory,
  Order,
  Payment,
} from "@uniserve/shared-types";

// ---- Cafeterias ----

interface CafeteriaListResponse {
  cafeterias: Cafeteria[];
  total: number;
}

/** Fetch all active cafeterias. For students, backend filters to student cafeterias. */
export async function getCafeterias(): Promise<Cafeteria[]> {
  const data = await apiClient.get<CafeteriaListResponse>("/cafeterias");
  return data.cafeterias ?? [];
}

// ---- Menu Items ----

interface MenuItemListResponse {
  items: MenuItem[];
  total: number;
}

export interface MenuItemsParams {
  category?: MenuCategory;
  is_available?: boolean;
  search?: string;
}

/** Fetch menu items for a specific cafeteria with optional filters. */
export async function getMenuItems(
  cafeteriaId: string,
  params?: MenuItemsParams,
): Promise<{ items: MenuItem[]; total: number }> {
  const qp = new URLSearchParams();
  if (params?.category) qp.append("category", params.category);
  if (params?.is_available !== undefined) qp.append("is_available", String(params.is_available));
  if (params?.search) qp.append("search", params.search);
  const qs = qp.toString();
  return apiClient.get<MenuItemListResponse>(
    `/cafeterias/${cafeteriaId}/menu-items${qs ? `?${qs}` : ""}`,
  );
}

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

// ---- Notifications ----

interface NotificationListResponse {
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

export async function getNotifications(params?: NotificationParams): Promise<Notification[]> {
  const queryParams = new URLSearchParams();
  if (params?.unread_only !== undefined) queryParams.append("unread_only", String(params.unread_only));
  if (params?.limit) queryParams.append("limit", String(params.limit));
  const qs = queryParams.toString();
  const data = await apiClient.get<NotificationListResponse>(
    `/notifications${qs ? `?${qs}` : ""}`,
  );
  return data.items ?? [];
}

export async function getUnreadNotificationCount(): Promise<number> {
  const response = await apiClient.get<{ unread_count: number }>("/notifications/unread-count");
  return response.unread_count;
}
