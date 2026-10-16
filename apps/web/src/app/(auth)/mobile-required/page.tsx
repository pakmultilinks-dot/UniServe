/**
 * UniServe — Mobile Required Page
 *
 * Displayed when a student or faculty member logs into the web dashboard.
 * Explains that ordering is available through the UniServe mobile app and
 * tells the user exactly how to get it (university distribution — there is
 * no public store listing yet, so no dead download button).
 *
 * This page is intentionally NOT part of /dashboard — it lives in the
 * (auth) route group so it renders with the centred auth layout.
 */

"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { LguSeal } from "@/components/LguBrand";
import { Button } from "@/components/ui/Button";

export default function MobileRequiredPage() {
  const { user, logout } = useAuth();
  const router = useRouter();

  const handleLogout = async () => {
    await logout();
    router.push("/login");
  };

  return (
    <main className="min-h-screen flex items-center justify-center bg-[var(--bg-secondary)] px-4 py-8">
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

        {/* Card */}
        <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl shadow-card p-6 sm:p-8 text-center">
          {/* Phone icon */}
          <div className="flex justify-center mb-4">
            <div className="w-14 h-14 rounded-full bg-brand-700/10 flex items-center justify-center">
              <svg
                className="w-7 h-7 text-brand-700 dark:text-brand-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={1.8}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z"
                />
              </svg>
            </div>
          </div>

          <h2 className="text-lg font-semibold text-[var(--text-primary)]">
            Use the Mobile App
          </h2>
          <p className="mt-2 text-sm text-[var(--text-muted)]">
            Ordering meals, snacks, and drinks is available through the
            UniServe mobile application.
          </p>

          {user && (
            <p className="mt-3 text-sm text-[var(--text-muted)]">
              Signed in as{" "}
              <span className="font-medium text-[var(--text-primary)]">
                {user.university_email}
              </span>{" "}
              ({user.role === "student" ? "Student" : "Faculty"})
            </p>
          )}

          {/* Mobile app availability */}
          <div className="mt-6 p-4 bg-[var(--bg-secondary)] border border-[var(--border-default)] rounded-lg text-left">
            <p className="text-sm font-semibold text-[var(--text-primary)] mb-1">
              How to get the mobile app
            </p>
            <p className="text-sm text-[var(--text-muted)]">
              The UniServe app is distributed by the university and is not on
              public app stores yet. Ask at your cafeteria counter or contact
              the university IT helpdesk for the install link, then sign in
              with the same account you just created.
            </p>
          </div>

          {/* Logout */}
          <div className="mt-6">
            <Button
              variant="secondary"
              size="lg"
              onClick={handleLogout}
              className="w-full"
            >
              Sign Out
            </Button>
          </div>
        </div>
      </div>
    </main>
  );
}
