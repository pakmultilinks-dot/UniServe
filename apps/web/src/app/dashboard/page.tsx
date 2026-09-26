/**
 * UniServe — Dashboard Page
 *
 * Minimal authenticated landing page. Shows user info and
 * role-based placeholder content. Feature dashboards (cafeteria,
 * admin, staff) will be built in future phases.
 */

"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/contexts/AuthContext";

export default function DashboardPage() {
  const { user, isAuthenticated, isLoading, logout } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [isLoading, isAuthenticated, router]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="text-gray-500">Loading…</p>
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">
          Welcome, {user.first_name} {user.last_name}
        </h2>
        <p className="text-gray-600 mt-1">
          Role: <span className="font-medium">{user.role}</span>
        </p>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <p className="text-gray-500">
          Dashboard features will be implemented in future phases.
        </p>
      </div>

      <button
        onClick={() => logout()}
        className="px-4 py-2 text-sm text-red-600 hover:text-red-800 underline"
      >
        Sign out
      </button>
    </div>
  );
}
