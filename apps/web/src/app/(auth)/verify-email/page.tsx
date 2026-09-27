/**
 * UniServe — Email Verification Page
 *
 * OTP-based email verification after registration.
 * 6-digit code entry with auto-submit, resend timer, and success redirect.
 */

"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Suspense } from "react";
import Link from "next/link";
import { verifyOtp, resendOtp } from "@/lib/api";
import { LguSeal } from "@/components/LguBrand";
import { Button } from "@/components/ui/Button";

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
      autoComplete="one-time-code"
    />
  );
}

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const userId = searchParams.get("userId") || "";

  const [otp, setOtp] = useState(["", "", "", "", "", ""]);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(60);
  const [canResend, setCanResend] = useState(false);
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  // Countdown timer for resend
  useEffect(() => {
    if (resendCooldown <= 0) {
      setCanResend(true);
      return;
    }
    const timer = setTimeout(() => setResendCooldown((c) => c - 1), 1000);
    return () => clearTimeout(timer);
  }, [resendCooldown]);

  const handleOtpChange = useCallback(
    (index: number, value: string) => {
      if (value.length > 1) value = value.slice(-1);
      const newOtp = [...otp];
      newOtp[index] = value;
      setOtp(newOtp);

      // Auto-focus next input
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

  const verifyCode = useCallback(
    async (code: string) => {
      if (!userId) {
        setError("Missing user ID. Please register again.");
        return;
      }
      setError(null);
      setIsLoading(true);
      try {
        await verifyOtp({
          user_id: userId,
          otp: code,
          purpose: "email_verification",
        });
        setSuccess("Email verified successfully! Redirecting to sign in...");
        setTimeout(() => router.push("/login"), 2000);
      } catch (err: unknown) {
        const message =
          err instanceof Error
            ? err.message
            : "Verification failed. Please check your code.";
        setError(message);
        setOtp(["", "", "", "", "", ""]);
        inputRefs.current[0]?.focus();
      } finally {
        setIsLoading(false);
      }
    },
    [userId, router],
  );

  // Auto-submit when all 6 digits entered
  useEffect(() => {
    const code = otp.join("");
    if (code.length === 6 && !isLoading) {
      verifyCode(code);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [otp, isLoading]);

  const handleResend = async () => {
    if (!userId || !canResend) return;
    setError(null);
    try {
      await resendOtp({ user_id: userId, purpose: "email_verification" });
      setResendCooldown(60);
      setCanResend(false);
      setSuccess("A new code has been sent to your email.");
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to resend code.";
      setError(message);
    }
  };

  if (!userId) {
    return (
      <div className="w-full max-w-md animate-fade-in">
        <div className="text-center mb-8">
          <div className="flex justify-center mb-4">
            <LguSeal size={56} />
          </div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">
            Verify Email
          </h1>
        </div>
        <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl shadow-card p-6 sm:p-8 text-center">
          <p className="text-[var(--text-muted)] mb-4">
            No verification session found. Please register first.
          </p>
          <Link href="/register">
            <Button variant="primary" className="w-full">
              Go to Registration
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
          Verify Your Email
        </h1>
        <p className="mt-1 text-sm text-[var(--text-muted)]">
          Enter the 6-digit code sent to your university email
        </p>
      </div>

      {/* OTP card */}
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

        {/* OTP input grid */}
        <div className="flex justify-center gap-2 mb-6">
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

        {/* Loading state */}
        {isLoading && (
          <p className="text-center text-sm text-[var(--text-muted)] mb-4">
            Verifying your code...
          </p>
        )}

        {/* Resend */}
        <div className="text-center mb-6">
          {canResend ? (
            <button
              type="button"
              onClick={handleResend}
              className="text-sm font-semibold text-brand-700 dark:text-brand-400 hover:text-brand-600 dark:hover:text-brand-300 transition-colors"
            >
              Resend Code
            </button>
          ) : (
            <p className="text-sm text-[var(--text-muted)]">
              Resend code in {resendCooldown}s
            </p>
          )}
        </div>
      </div>

      {/* Back to login */}
      <p className="mt-6 text-center text-sm text-[var(--text-muted)]">
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

export default function VerifyEmailPage() {
  return (
    <Suspense
      fallback={
        <div className="text-[var(--text-muted)] flex items-center justify-center min-h-[200px]">
          Loading...
        </div>
      }
    >
      <VerifyEmailContent />
    </Suspense>
  );
}
