/**
 * UniServe — TypeScript type definitions
 *
 * Shared types for the mobile application.
 * These will be expanded as features are implemented.
 */

export type UserRole = "student" | "faculty" | "cafeteria_staff" | "cafeteria_manager" | "admin";

export interface User {
  id: string;
  email: string;
  firstName: string;
  lastName: string;
  role: UserRole;
  createdAt: string;
}

export interface ApiResponse<T> {
  data: T;
  message?: string;
}

export interface ApiError {
  detail: string;
  status_code: number;
}
