/**
 * UniServe — Forgot Password Page
 *
 * Step 1 of password reset: request a reset code via university email.
 * On success, redirects to reset-password page with userId and email params.
 */

"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { requestPasswordReset } from "@/lib/api";
import { LguSeal } from "@/components/LguBrand";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

export default function ForgotPasswordPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      await requestPasswordReset({ university_email: email });
      // Redirect to reset-password page with email param
      router.push(`/reset-password?email=${encodeURIComponent(email)}`);
    } catch (err: unknown) {
      // Don't reveal whether the email exists
      const message =
        err instanceof Error
          ? err.message
          : "Something went wrong. Please try again.";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="w-full max-w-md animate-fade-in">
      {/* Brand header */}
      <div className="text-center mb-8">
        <div className="flex justify-center mb-4">
          <LguSeal size={56} />
        </div>
        <h1 className="text-2xl font-bold text-[var(--text-primary)] tracking-tight">
          Reset Password
        </h1>
        <p className="mt-1 text-sm text-[var(--text-muted)]">
          We&apos;ll send you a code to reset your password
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

        <form onSubmit={handleSubmit} className="space-y-4">
          <p className="text-sm text-[var(--text-muted)]">
            Enter the university email associated with your account. We&apos;ll
            send a 6-digit verification code to that address.
          </p>

          <Input
            label="University Email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
            placeholder="your.name@lgu.edu.pk"
          />

          <Button
            type="submit"
            variant="primary"
            size="lg"
            loading={isLoading}
            className="w-full"
          >
            {isLoading ? "Sending Code..." : "Send Reset Code"}
          </Button>
        </form>
      </div>

      {/* Back to login */}
      <p className="mt-6 text-center text-sm text-[var(--text-muted)]">
        Remember your password?{" "}
        <Link
          href="/login"
          className="font-semibold text-brand-700 dark:text-brand-400 hover:text-brand-600 dark:hover:text-brand-300 transition-colors"
        >
          Sign in
        </Link>
      </p>
    </div>
  );
}
