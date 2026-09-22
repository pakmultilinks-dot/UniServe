/**
 * UniServe — Authentication Types
 *
 * TypeScript types for authentication, authorization, and user management.
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
  expires_in: number; // seconds
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
  device_info?: string;
  ip_address?: string;
  created_at: string;
  last_activity_at: string;
  is_current: boolean;
}

export interface SessionListResponse {
  sessions: Session[];
}

// ---- Auth Context ----

export interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  isEmailVerified: boolean;
}
