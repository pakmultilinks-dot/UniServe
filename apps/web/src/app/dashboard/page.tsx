/**
 * UniServe — Dashboard Page
 *
 * Authenticated landing page with real API data:
 * - Welcome greeting with user role badge
 * - Quick stats: cafeterias, active orders, unread notifications
 * - Recent orders list with status chips
 * - Recent notifications list
 * - Empty states for each section when no data
 */

"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import {
  getCafeterias,
  getMyCafeterias,
  getOrders,
  getCafeteriaOrders,
  getNotifications,
  getApiErrorInfo,
} from "@/lib/api";
import type { ApiErrorInfo } from "@/lib/api";
import type { Order, Notification, Cafeteria } from "@uniserve/shared-types";
import { Avatar } from "@/components/ui/Avatar";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadErrorState } from "@/components/ui/LoadErrorState";
import { StatusBadge } from "@/components/ui/StatusBadge";

/* Stat card */
function StatCard({
  label,
  value,
  icon,
}: {
  label: string;
  value: string | number;
  icon: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-4 bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl p-5 shadow-card">
      <div className="flex-shrink-0 w-11 h-11 rounded-lg bg-brand-50 dark:bg-brand-900/30 flex items-center justify-center text-brand-700 dark:text-brand-400">
        {icon}
      </div>
      <div>
        <p className="text-2xl font-bold text-[var(--text-primary)] leading-none">
          {value}
        </p>
        <p className="text-sm text-[var(--text-muted)] mt-0.5">{label}</p>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { user, isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  const [cafeterias, setCafeterias] = useState<Cafeteria[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [dataLoading, setDataLoading] = useState(true);
  /* Phase 46 — per-source failure states. Each section keeps its own error
     so one failed request never masquerades as a zero/empty section. */
  const [cafeteriasError, setCafeteriasError] = useState<ApiErrorInfo | null>(null);
  const [ordersError, setOrdersError] = useState<ApiErrorInfo | null>(null);
  const [notificationsError, setNotificationsError] = useState<ApiErrorInfo | null>(null);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [isLoading, isAuthenticated, router]);

  const loadDashboardData = useCallback(async () => {
    if (!isAuthenticated || !user) return;
    setDataLoading(true);

    const results = await Promise.allSettled([
      // Phase 56 — home is an ordering surface: only ACTIVE cafeterias
      // are offered. Inactive cafeterias stay visible to admins on the
      // Cafeterias admin page.
      getCafeterias({ isActive: true }),
      getNotifications({ limit: 5 }),
    ]);

    // P3-11 — staff/manager scope: the "Cafeterias" stat and the order
    // aggregation below reflect the user's actual assignment, not the
    // university-wide list. Admin keeps the global view. If assignment
    // info is unavailable, fall back to the previous all-cafeterias view.
    let visibleCafeterias: Cafeteria[] = [];
    if (results[0].status === "fulfilled") {
      visibleCafeterias = results[0].value;
      setCafeteriasError(null);
    } else {
      // Phase 46 — surface the failure; never present it as zero cafeterias.
      setCafeteriasError(getApiErrorInfo(results[0].reason));
    }
    const isDashboardStaff = [
      "cafeteria_staff",
      "cafeteria_manager",
    ].includes(user.role);
    if (isDashboardStaff && visibleCafeterias.length > 0) {
      try {
        const assigned = await getMyCafeterias();
        if (assigned.length > 0) {
          visibleCafeterias = visibleCafeterias.filter((c) =>
            assigned.includes(c.id),
          );
        }
      } catch {
        // Best-effort: keep the full cafeteria list if assignment lookup fails.
      }
    }
    setCafeterias(visibleCafeterias);
    if (results[1].status === "fulfilled") {
      setNotifications(results[1].value.items);
      setUnreadCount(results[1].value.unread_count);
      setNotificationsError(null);
    } else {
      // Phase 46 — keep any previously loaded notifications on screen and
      // surface the failure instead of a silent "0 unread".
      setNotificationsError(getApiErrorInfo(results[1].reason));
    }

    // Fetch orders: students get their own orders; staff/admin get cafeteria orders
    const isStaff = ["cafeteria_staff", "cafeteria_manager", "university_admin"].includes(user.role);
    try {
      if (isStaff && visibleCafeterias.length > 0) {
        // Aggregate orders from the cafeterias this user can actually
        // access (scoped for staff/manager, all for admin).
        const allCafeOrders = await Promise.allSettled(
          visibleCafeterias.map((c) => getCafeteriaOrders(c.id)),
        );
        const merged: Order[] = [];
        let rejected = 0;
        for (const r of allCafeOrders) {
          if (r.status === "fulfilled") {
            merged.push(...((r.value.orders ?? []) as Order[]));
          } else {
            rejected += 1;
          }
        }
        // Phase 46 — if every cafeteria queue failed, surface the failure
        // instead of rendering an empty "Recent Orders" section. Partial
        // failures still show the real data that did load.
        if (rejected > 0 && merged.length === 0) {
          const first = allCafeOrders.find((r) => r.status === "rejected");
          if (first && first.status === "rejected") {
            setOrdersError(getApiErrorInfo(first.reason));
          }
        } else {
          setOrdersError(null);
        }
        merged.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
        setOrders(merged);
      } else {
        // Backend GET /orders has no limit param (7-day window default);
        // retain all orders for the active count; limit only the recent list.
        const myOrders = await getOrders();
        setOrders(myOrders);
        setOrdersError(null);
      }
    } catch (err) {
      // Phase 46 — keep any previously loaded orders on screen and surface
      // the failure; never present a broken request as "No orders yet".
      setOrdersError(getApiErrorInfo(err));
    }

    setDataLoading(false);
  }, [isAuthenticated, user]);

  useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData]);

  if (isLoading || !user) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-6 h-6 border-2 border-brand-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const activeOrders = orders.filter(
    (o) => o.status === "pending" || o.status === "preparing" || o.status === "ready",
  );

  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return "Good morning";
    if (hour < 17) return "Good afternoon";
    return "Good evening";
  };

  const roleLabel = user.role
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());

  const formatDate = (iso: string) => {
    if (!iso) return "";
    // Time-only string like "18:18"
    if (/^\d{1,2}:\d{2}$/.test(iso)) {
      const [h, m] = iso.split(":").map(Number);
      const ampm = h >= 12 ? "PM" : "AM";
      const h12 = h % 12 || 12;
      return `${h12}:${String(m).padStart(2, "0")} ${ampm}`;
    }
    // Date-only string like "2026-09-30"
    if (/^\d{4}-\d{2}-\d{2}$/.test(iso)) {
      const [y, mo, d] = iso.split("-").map(Number);
      return new Date(y, mo - 1, d).toLocaleDateString("en-US", {
        month: "short", day: "numeric",
      });
    }
    try {
      return new Date(iso).toLocaleDateString("en-US", {
        month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
      });
    } catch { return iso; }
  };

  const formatCurrency = (amount: number, currency: string) => {
    return `${currency} ${(amount / 100).toFixed(2)}`;
  };

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Welcome header */}
      <div className="flex items-center gap-4">
        <Avatar
          firstName={user.first_name}
          lastName={user.last_name}
          size="lg"
        />
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">
            {getGreeting()}, {user.first_name}
          </h1>
          <div className="flex items-center gap-2 mt-1">
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-brand-50 dark:bg-brand-900/30 text-brand-700 dark:text-brand-400">
              {roleLabel}
            </span>
            <span className="text-sm text-[var(--text-muted)]">
              {user.university_email}
            </span>
          </div>
        </div>
      </div>

      {/* Quick stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard
          label={
            ["cafeteria_staff", "cafeteria_manager"].includes(user.role)
              ? "My Cafeterias"
              : "Cafeterias"
          }
          value={cafeteriasError ? "—" : cafeterias.length}
          icon={
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 21v-7.5a.75.75 0 01.75-.75h3a.75.75 0 01.75.75V21m-4.5 0H2.36m11.14 0H18m0 0h3.64m-1.39 0V9.349m-16.5 11.65V9.35m0 0a3.001 3.001 0 003.75-.615A2.993 2.993 0 009.75 9.75c.896 0 1.7-.393 2.25-1.016a2.993 2.993 0 002.25 1.016c.896 0 1.7-.393 2.25-1.016a3.001 3.001 0 003.75.614m-16.5 0a3.004 3.004 0 01-.621-4.72L4.318 3.44A1.5 1.5 0 015.378 3h13.243a1.5 1.5 0 011.06.44l1.19 1.189a3 3 0 01-.621 4.72m-13.5 8.65h3.75a.75.75 0 00.75-.75V13.5a.75.75 0 00-.75-.75H6.75a.75.75 0 00-.75.75v3.75c0 .415.336.75.75.75z" />
            </svg>
          }
        />
        <StatCard
          label="Active Orders"
          value={ordersError ? "—" : activeOrders.length}
          icon={
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25zM6.75 12h.008v.008H6.75V12zm0 3h.008v.008H6.75V15zm0 3h.008v.008H6.75V18z" />
            </svg>
          }
        />
        <StatCard
          label="Unread Notifications"
          value={notificationsError ? "—" : unreadCount}
          icon={
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
            </svg>
          }
        />
      </div>

      {/* Content grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Orders */}
        <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl shadow-card overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border-default)]">
            <h2 className="text-base font-semibold text-[var(--text-primary)]">
              Recent Orders
            </h2>
            {orders.length > 0 && (
              <Link
                href={`/dashboard/orders?cafeteria=${encodeURIComponent(orders[0].cafeteria_id)}`}
                className="text-sm font-medium text-brand-700 dark:text-brand-400 hover:text-brand-600 dark:hover:text-brand-300 transition-colors"
              >
                Open order queue
              </Link>
            )}
          </div>
          <div className="divide-y divide-[var(--border-default)]">
            {ordersError && orders.length > 0 && (
              <LoadErrorState
                compact
                error={ordersError}
                subject="recent orders"
                onRetry={() => loadDashboardData()}
                className="border-b border-[var(--border-default)]"
              />
            )}
            {dataLoading ? (
              <div className="p-6 space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="flex justify-between">
                    <div className="space-y-2 flex-1">
                      <div className="h-4 bg-[var(--bg-secondary)] rounded w-24 skeleton" />
                      <div className="h-3 bg-[var(--bg-secondary)] rounded w-36 skeleton" />
                    </div>
                    <div className="h-5 bg-[var(--bg-secondary)] rounded w-16 skeleton" />
                  </div>
                ))}
              </div>
            ) : ordersError && orders.length === 0 ? (
              <LoadErrorState
                compact
                error={ordersError}
                subject="recent orders"
                onRetry={() => loadDashboardData()}
                className="py-8"
              />
            ) : orders.length === 0 ? (
              <EmptyState
                icon={
                  <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25z" />
                  </svg>
                }
                title="No orders yet"
                description="When you place an order, it will appear here."
              />
            ) : (
              orders.slice(0, 5).map((order) => (
                <div
                  key={order.id}
                  className="flex items-center justify-between px-5 py-3.5 hover:bg-[var(--bg-secondary)] transition-colors"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-[var(--text-primary)]">
                        Order #{order.order_number}
                      </span>
                      <StatusBadge status={order.status} />
                    </div>
                    <p className="text-xs text-[var(--text-muted)] mt-0.5">
                      {order.items.length} item{order.items.length !== 1 ? "s" : ""} ·{" "}
                      {formatCurrency(order.total_amount, order.currency)} ·{" "}
                      {formatDate(order.order_date)}
                    </p>
                  </div>
                  <Link
                    href={`/dashboard/orders?cafeteria=${encodeURIComponent(order.cafeteria_id)}`}
                    className="ml-4 flex-shrink-0 text-xs font-medium text-brand-700 dark:text-brand-400 hover:text-brand-600"
                  >
                    View in queue
                  </Link>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Recent Notifications */}
        <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl shadow-card overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border-default)]">
            <h2 className="text-base font-semibold text-[var(--text-primary)]">
              Notifications
            </h2>
            {notifications.length > 0 && (
              <Link
                href="/dashboard/notifications"
                className="text-sm font-medium text-brand-700 dark:text-brand-400 hover:text-brand-600 dark:hover:text-brand-300 transition-colors"
              >
                View all
              </Link>
            )}
          </div>
          <div className="divide-y divide-[var(--border-default)]">
            {notificationsError && notifications.length > 0 && (
              <LoadErrorState
                compact
                error={notificationsError}
                subject="recent notifications"
                onRetry={() => loadDashboardData()}
                className="border-b border-[var(--border-default)]"
              />
            )}
            {dataLoading ? (
              <div className="p-6 space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="space-y-2">
                    <div className="h-4 bg-[var(--bg-secondary)] rounded w-40 skeleton" />
                    <div className="h-3 bg-[var(--bg-secondary)] rounded w-full skeleton" />
                  </div>
                ))}
              </div>
            ) : notificationsError && notifications.length === 0 ? (
              <LoadErrorState
                compact
                error={notificationsError}
                subject="recent notifications"
                onRetry={() => loadDashboardData()}
                className="py-8"
              />
            ) : notifications.length === 0 ? (
              <EmptyState
                icon={
                  <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
                  </svg>
                }
                title="No notifications"
                description="You're all caught up! Notifications about your orders will appear here."
              />
            ) : (
              notifications.map((n) => (
                <div
                  key={n.id}
                  className={`px-5 py-3.5 transition-colors ${!n.is_read ? "bg-brand-50/30 dark:bg-brand-900/10" : ""}`}
                >
                  <div className="flex items-start gap-3">
                    {!n.is_read && (
                      <div className="mt-1.5 flex-shrink-0 w-2 h-2 rounded-full bg-brand-600" />
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-[var(--text-primary)]">
                        {n.title}
                      </p>
                      <p className="text-xs text-[var(--text-muted)] mt-0.5 line-clamp-2">
                        {n.body}
                      </p>
                      <p className="text-xs text-[var(--text-muted)] mt-1">
                        {formatDate(n.created_at)}
                      </p>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Cafeterias quick view — Phase 46: a failed cafeterias request is
          surfaced here instead of silently hiding the whole section. */}
      {cafeteriasError && cafeterias.length === 0 ? (
        <LoadErrorState
          compact
          error={cafeteriasError}
          subject="cafeterias"
          onRetry={() => loadDashboardData()}
        />
      ) : cafeterias.length > 0 && (
        <div>
          <h2 className="text-base font-semibold text-[var(--text-primary)] mb-3">
            Cafeterias
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {cafeterias.slice(0, 6).map((caf) => (
              <Link
                key={caf.id}
                href="/dashboard/cafeterias"
                className="flex items-center gap-3 bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl p-4 shadow-card hover:shadow-card-hover hover:border-brand-200 dark:hover:border-brand-800 transition-all"
              >
                <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-brand-50 dark:bg-brand-900/30 flex items-center justify-center">
                  <svg className="w-5 h-5 text-brand-700 dark:text-brand-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 21v-7.5a.75.75 0 01.75-.75h3a.75.75 0 01.75.75V21m-4.5 0H2.36m11.14 0H18m0 0h3.64m-1.39 0V9.349m-16.5 11.65V9.35m0 0a3.001 3.001 0 003.75-.615A2.993 2.993 0 009.75 9.75c.896 0 1.7-.393 2.25-1.016a2.993 2.993 0 002.25 1.016c.896 0 1.7-.393 2.25-1.016a3.001 3.001 0 003.75.614m-16.5 0a3.004 3.004 0 01-.621-4.72L4.318 3.44A1.5 1.5 0 015.378 3h13.243a1.5 1.5 0 011.06.44l1.19 1.189a3 3 0 01-.621 4.72m-13.5 8.65h3.75a.75.75 0 00.75-.75V13.5a.75.75 0 00-.75-.75H6.75a.75.75 0 00-.75.75v3.75c0 .415.336.75.75.75z" />
                  </svg>
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-[var(--text-primary)] truncate">
                    {caf.name}
                  </p>
                  <p className="text-xs text-[var(--text-muted)] truncate">
                    {caf.location || "Campus cafeteria"}
                  </p>
                </div>
                <div className="ml-auto flex-shrink-0">
                  {/* Status is text, not color alone (WCAG 1.4.1) */}
                  <span
                    className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                      caf.is_active
                        ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300"
                        : "bg-neutral-200 text-neutral-600 dark:bg-neutral-700 dark:text-neutral-300"
                    }`}
                  >
                    {caf.is_active ? "Open" : "Closed"}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
