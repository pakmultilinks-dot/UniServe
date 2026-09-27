/**
 * UniServe — Register Page
 * LGU-branded registration for students and faculty.
 */

"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import { LguSeal } from "@/components/LguBrand";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

export default function RegisterPage() {
  const router = useRouter();
  const { register } = useAuth();

  const [form, setForm] = useState({
    firstName: "",
    lastName: "",
    universityId: "",
    email: "",
    password: "",
    confirmPassword: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (form.password !== form.confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    if (form.password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }

    setIsLoading(true);
    try {
      const result = await register({
        firstName: form.firstName,
        lastName: form.lastName,
        universityId: form.universityId,
        email: form.email,
        password: form.password,
      });
      setSuccess(
        `Account created! A verification code has been sent to ${result.email}. Please verify your email to activate your account.`
      );
      setTimeout(() => {
        router.push(`/verify-email?userId=${result.userId}`);
      }, 2000);
    } catch (err: unknown) {
      const message =
        err instanceof Error
          ? err.message
          : "Registration failed. Please try again.";
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
          Create Account
        </h1>
        <p className="mt-1 text-sm text-[var(--text-muted)]">
          Join Lahore Garrison University&apos;s cafeteria platform
        </p>
      </div>

      {/* Register card */}
      <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl shadow-card p-6 sm:p-8">
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

          {/* Success alert */}
          {success && (
            <div
              className="flex items-start gap-2.5 p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg text-sm text-green-700 dark:text-green-400"
              role="status"
            >
              <svg className="w-4 h-4 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span>{success}</span>
            </div>
          )}

          {/* Name fields */}
          <div className="grid grid-cols-2 gap-3">
            <Input
              label="First Name"
              name="firstName"
              type="text"
              value={form.firstName}
              onChange={handleChange}
              required
              autoComplete="given-name"
            />
            <Input
              label="Last Name"
              name="lastName"
              type="text"
              value={form.lastName}
              onChange={handleChange}
              required
              autoComplete="family-name"
            />
          </div>

          <Input
            label="University ID"
            name="universityId"
            type="text"
            value={form.universityId}
            onChange={handleChange}
            required
            placeholder="e.g., FA22-BSE-001"
          />

          <Input
            label="University Email"
            name="email"
            type="email"
            value={form.email}
            onChange={handleChange}
            required
            autoComplete="email"
            placeholder="your.name@lgu.edu.pk"
          />

          <Input
            label="Password"
            name="password"
            type="password"
            value={form.password}
            onChange={handleChange}
            required
            minLength={8}
            placeholder="Minimum 8 characters"
            showPasswordToggle
          />

          <Input
            label="Confirm Password"
            name="confirmPassword"
            type="password"
            value={form.confirmPassword}
            onChange={handleChange}
            required
            placeholder="Re-enter your password"
            showPasswordToggle
          />

          <p className="text-xs text-[var(--text-muted)]">
            This platform is for authorized LGU students and faculty only.
            By registering, you agree to the university&apos;s acceptable use policy.
          </p>

          <Button
            type="submit"
            variant="primary"
            size="lg"
            loading={isLoading}
            className="w-full"
          >
            {isLoading ? "Creating Account..." : "Create Account"}
          </Button>
        </form>
      </div>

      {/* Login link */}
      <p className="mt-6 text-center text-sm text-[var(--text-muted)]">
        Already have an account?{" "}
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
