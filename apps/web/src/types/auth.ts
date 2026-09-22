/**
 * UniServe — Web Authentication Types
 *
 * TypeScript types for web application authentication.
 */

// ---- Enums ----

export type UserCategory = "student" | "faculty";

export type UserRole =
  | "student"
  | "faculty"
  | "cafeteria_staff"
  | "cafeteria_manager"
  | "university_admin";

export type AccountStatus =
  | "pending_verification"
  | "active"
  | "suspended"
  | "deleted";

export type OTPPurpose = "email_verification" | "password_reset";

// ---- User ----

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

// ---- Auth ----

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  expires_in: number;
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

export interface LoginRequest {
  university_email: string;
  password: string;
}

// ---- Auth State ----

export interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  hasRole: (role: UserRole | UserRole[]) => boolean;
}
