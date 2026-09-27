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
  MenuCategory,
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
  try {
    const data = await apiClient.get<DailyMenu | null>(
      `/cafeterias/${cafeteriaId}/daily-menus/today`,
    );
    return data;
  } catch {
    return null;
  }
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

// ---- Orders ----

interface OrderListResponse {
  orders: Order[];
  total: number;
}

export interface Order {
  id: string;
  order_number: string;
  status: string;
  total_amount: number;
  currency: string;
  items: OrderItem[];
  cafeteria_name: string;
  created_at: string;
  updated_at: string;
}

export interface OrderItem {
  id: string;
  menu_item_name: string;
  quantity: number;
  unit_price: number;
  subtotal: number;
}

export interface OrderParams {
  status?: string;
  limit?: number;
}

export async function getOrders(params?: OrderParams): Promise<Order[]> {
  const queryParams = new URLSearchParams();
  if (params?.status) queryParams.append("status", params.status);
  if (params?.limit) queryParams.append("limit", String(params.limit));
  const qs = queryParams.toString();
  const data = await apiClient.get<OrderListResponse>(`/orders${qs ? `?${qs}` : ""}`);
  return data.orders ?? [];
}

// ---- Notifications ----

interface NotificationListResponse {
  notifications: Notification[];
  total: number;
}

export interface Notification {
  id: string;
  title: string;
  body: string;
  type: string;
  is_read: boolean;
  created_at: string;
}

export interface NotificationParams {
  is_read?: boolean;
  limit?: number;
}

export async function getNotifications(params?: NotificationParams): Promise<Notification[]> {
  const queryParams = new URLSearchParams();
  if (params?.is_read !== undefined) queryParams.append("is_read", String(params.is_read));
  if (params?.limit) queryParams.append("limit", String(params.limit));
  const qs = queryParams.toString();
  const data = await apiClient.get<NotificationListResponse>(
    `/notifications${qs ? `?${qs}` : ""}`,
  );
  return data.notifications ?? [];
}

export async function getUnreadNotificationCount(): Promise<number> {
  const response = await apiClient.get<{ count: number }>("/notifications/unread-count");
  return response.count;
}
