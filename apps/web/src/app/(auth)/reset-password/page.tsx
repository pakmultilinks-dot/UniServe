/**
 * UniServe — Reset Password Page
 *
 * Step 2 of password reset flow: enter the OTP code and new password.
 * Requires `email` search param from the forgot-password redirect.
 */

"use client";

import React, { useState, useRef, useCallback, useEffect } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Suspense } from "react";
import Link from "next/link";
import { confirmPasswordReset } from "@/lib/api";
import { LguSeal } from "@/components/LguBrand";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

function OTPDigitInput({
  value,
  onChange,
  onKeyDown,
  index,
  inputRef,
}: {
  value: string;
  onChange: (val: string) => void;
  onKeyDown: (e: React.KeyboardEvent) => void;
  index: number;
  inputRef: (el: HTMLInputElement | null) => void;
}) {
  return (
    <input
      ref={inputRef}
      type="text"
      inputMode="numeric"
      maxLength={1}
      value={value}
      onChange={(e) => {
        const val = e.target.value.replace(/\D/g, "");
        onChange(val);
      }}
      onKeyDown={onKeyDown}
      className="w-12 h-14 text-center text-xl font-semibold bg-[var(--bg-secondary)] border border-[var(--border-default)] rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500 transition-colors"
      aria-label={`Digit ${index + 1}`}
    />
  );
}

function ResetPasswordContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const email = searchParams.get("email") || "";

  const [otp, setOtp] = useState(["", "", "", "", "", ""]);
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  const handleOtpChange = useCallback(
    (index: number, value: string) => {
      if (value.length > 1) value = value.slice(-1);
      const newOtp = [...otp];
      newOtp[index] = value;
      setOtp(newOtp);
      if (value && index < 5) {
        inputRefs.current[index + 1]?.focus();
      }
    },
    [otp],
  );

  const handleKeyDown = useCallback(
    (index: number, e: React.KeyboardEvent) => {
      if (e.key === "Backspace" && !otp[index] && index > 0) {
        inputRefs.current[index - 1]?.focus();
      }
      if (e.key === "ArrowLeft" && index > 0) {
        inputRefs.current[index - 1]?.focus();
      }
      if (e.key === "ArrowRight" && index < 5) {
        inputRefs.current[index + 1]?.focus();
      }
    },
    [otp],
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const code = otp.join("");
    if (code.length !== 6) {
      setError("Please enter the complete 6-digit code.");
      return;
    }
    if (newPassword.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    if (!email) {
      setError("Missing email. Please start the reset process again.");
      return;
    }

    setIsLoading(true);
    try {
      await confirmPasswordReset({
        university_email: email,
        otp: code,
        new_password: newPassword,
      });
      setSuccess(
        "Password reset successfully! Redirecting to sign in...",
      );
      setTimeout(() => router.push("/login"), 2000);
    } catch (err: unknown) {
      const message =
        err instanceof Error
          ? err.message
          : "Password reset failed. Please check your code and try again.";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  if (!email) {
    return (
      <div className="w-full max-w-md animate-fade-in">
        <div className="text-center mb-8">
          <div className="flex justify-center mb-4">
            <LguSeal size={56} />
          </div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">
            Reset Password
          </h1>
        </div>
        <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl shadow-card p-6 sm:p-8 text-center">
          <p className="text-[var(--text-muted)] mb-4">
            No reset session found. Please start the password reset process.
          </p>
          <Link href="/forgot-password">
            <Button variant="primary" className="w-full">
              Reset Password
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full max-w-md animate-fade-in">
      {/* Brand header */}
      <div className="text-center mb-8">
        <div className="flex justify-center mb-4">
          <LguSeal size={56} />
        </div>
        <h1 className="text-2xl font-bold text-[var(--text-primary)]">
          Set New Password
        </h1>
        <p className="mt-1 text-sm text-[var(--text-muted)]">
          Enter the code sent to <span className="font-medium text-[var(--text-primary)]">{email}</span>
        </p>
      </div>

      {/* Card */}
      <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl shadow-card p-6 sm:p-8">
        {/* Error */}
        {error && (
          <div
            className="flex items-start gap-2.5 p-3 mb-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-700 dark:text-red-400"
            role="alert"
          >
            <svg className="w-4 h-4 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
            <span>{error}</span>
          </div>
        )}

        {/* Success */}
        {success && (
          <div
            className="flex items-start gap-2.5 p-3 mb-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg text-sm text-green-700 dark:text-green-400"
            role="status"
          >
            <svg className="w-4 h-4 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>{success}</span>
          </div>
        )}

        {!success && (
          <form onSubmit={handleSubmit} className="space-y-5">
            {/* OTP section */}
            <div>
              <label className="block text-sm font-medium text-[var(--text-primary)] mb-2">
                Verification Code
              </label>
              <div className="flex justify-center gap-2">
                {otp.map((digit, i) => (
                  <OTPDigitInput
                    key={i}
                    index={i}
                    value={digit}
                    onChange={(v) => handleOtpChange(i, v)}
                    onKeyDown={(e) => handleKeyDown(i, e)}
                    inputRef={(el) => {
                      inputRefs.current[i] = el;
                    }}
                  />
                ))}
              </div>
            </div>

            {/* Password fields */}
            <Input
              label="New Password"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              minLength={8}
              placeholder="Minimum 8 characters"
              showPasswordToggle
            />

            <Input
              label="Confirm New Password"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              placeholder="Re-enter your new password"
              showPasswordToggle
            />

            <Button
              type="submit"
              variant="primary"
              size="lg"
              loading={isLoading}
              className="w-full"
            >
              {isLoading ? "Resetting Password..." : "Reset Password"}
            </Button>
          </form>
        )}

        {success && (
          <Link href="/login">
            <Button variant="primary" size="lg" className="w-full">
              Go to Sign In
            </Button>
          </Link>
        )}
      </div>

      {/* Back links */}
      <p className="mt-6 text-center text-sm text-[var(--text-muted)]">
        <Link
          href="/forgot-password"
          className="font-semibold text-brand-700 dark:text-brand-400 hover:text-brand-600 dark:hover:text-brand-300 transition-colors"
        >
          Request a new code
        </Link>
        {" · "}
        <Link
          href="/login"
          className="font-semibold text-brand-700 dark:text-brand-400 hover:text-brand-600 dark:hover:text-brand-300 transition-colors"
        >
          Back to Sign In
        </Link>
      </p>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense
      fallback={
        <div className="text-[var(--text-muted)] flex items-center justify-center min-h-[200px]">
          Loading...
        </div>
      }
    >
      <ResetPasswordContent />
    </Suspense>
  );
}
