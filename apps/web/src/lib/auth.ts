/**
 * UniServe — Web Authentication API Client
 *
 * @deprecated Import from "../lib/api" instead.
 * This file is kept for backward compatibility and re-exports from the
 * unified API client. Will be removed in a future cleanup pass.
 */

export {
  login,
  register,
  refreshTokens,
  getCurrentUser,
  logout,
  requestPasswordReset,
  verifyOtp,
  resendOtp,
  getSessions,
} from "./api";

export type {
  LoginRequest,
  LoginResponse,
  RegisterRequest,
  RegisterResponse,
  TokenPair,
  User,
  OTPVerifyRequest,
  OTPResendRequest,
  OTPResponse,
  PasswordResetRequest,
  SessionListResponse,
} from "@uniserve/shared-types";
