/**
 * UniServe — Data API Service (Mobile)
 *
 * API calls for cafeterias, orders, and notifications.
 * Uses the shared ApiClient with auth injection.
 */

import { apiClient } from "./api";

// ---- Cafeterias ----

export interface Cafeteria {
  id: string;
  name: string;
  location: string;
  description: string;
  is_active: boolean;
  operating_hours: Record<string, { open: string; close: string }>;
}

export async function getCafeterias(): Promise<Cafeteria[]> {
  return apiClient.get<Cafeteria[]>("/cafeterias");
}

// ---- Orders ----

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
  return apiClient.get<Order[]>(`/orders${qs ? `?${qs}` : ""}`);
}

// ---- Notifications ----

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
  return apiClient.get<Notification[]>(`/notifications${qs ? `?${qs}` : ""}`);
}

export async function getUnreadNotificationCount(): Promise<number> {
  const response = await apiClient.get<{ count: number }>("/notifications/unread-count");
  return response.count;
}
