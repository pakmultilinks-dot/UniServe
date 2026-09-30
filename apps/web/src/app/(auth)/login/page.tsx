/**
 * UniServe — Login Page
 * LGU-branded authentication with institutional identity.
 */

"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import { LguBrand, LguSeal } from "@/components/LguBrand";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

export default function LoginPage() {
  const router = useRouter();
  const { login, isAuthenticated } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (isAuthenticated) {
      router.push("/dashboard");
    }
  }, [isAuthenticated, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      await login(email, password);
      router.push("/dashboard");
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Login failed. Please try again.";
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
          UniServe
        </h1>
        <p className="mt-1 text-sm text-[var(--text-muted)]">
          Lahore Garrison University
        </p>
      </div>

      {/* Login card */}
      <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl shadow-card p-6 sm:p-8">
        <div className="mb-6">
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">
            Sign in to your account
          </h2>
          <p className="mt-1 text-sm text-[var(--text-muted)]">
            Use your LGU university credentials
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Error alert */}
          {error && (
            <div
              className="flex items-start gap-2.5 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-700 dark:text-red-400"
              role="alert"
            >
              <svg className="w-4 h-4 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
              <span>{error}</span>
            </div>
          )}

          <Input
            label="University Email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
            placeholder="your.name@lgu.edu.pk"
          />

          <Input
            label="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="current-password"
            placeholder="Enter your password"
            showPasswordToggle
          />

          <div className="flex items-center justify-end">
            <Link
              href="/forgot-password"
              className="text-sm text-brand-700 dark:text-brand-400 hover:text-brand-600 dark:hover:text-brand-300 font-medium transition-colors"
            >
              Forgot password?
            </Link>
          </div>

          <Button
            type="submit"
            variant="primary"
            size="lg"
            loading={isLoading}
            className="w-full"
          >
            {isLoading ? "Signing in..." : "Sign In"}
          </Button>
        </form>
      </div>

      {/* Registration link */}
      <p className="mt-6 text-center text-sm text-[var(--text-muted)]">
        Don&apos;t have an account?{" "}
        <Link
          href="/register"
          className="font-semibold text-brand-700 dark:text-brand-400 hover:text-brand-600 dark:hover:text-brand-300 transition-colors"
        >
          Register here
        </Link>
      </p>
    </div>
  );
}
