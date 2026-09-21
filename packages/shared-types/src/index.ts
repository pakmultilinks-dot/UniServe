/**
 * UniServe — Shared Type Definitions
 *
 * Types shared across mobile, web, and API applications.
 * The backend remains the authoritative source for business rules.
 *
 * NOTE: Keep this package minimal. Only include types that genuinely
 * need to be shared across multiple applications.
 */

// ---- User & Authentication ----

export type UserRole =
  | "student"
  | "faculty"
  | "cafeteria_staff"
  | "cafeteria_manager"
  | "admin";

export type CafeteriaType = "student" | "faculty";

// ---- API Response ----

export interface ApiResponse<T> {
  data: T;
  message?: string;
}

export interface ApiError {
  detail: string;
  status_code: number;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

// ---- Common ----

export interface PaginatedQuery {
  page?: number;
  pageSize?: number;
  search?: string;
  sortBy?: string;
  sortOrder?: "asc" | "desc";
}
