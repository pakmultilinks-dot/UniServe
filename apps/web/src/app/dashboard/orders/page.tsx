"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import { getCafeterias, getMyCafeterias, getCafeteriaOrders, confirmOrder, prepareOrder, readyOrder, delayOrder, rejectOrder, collectOrder, managerCancelOrder, closeCafeteriaDay, getOrderDetail, getOrderEta, getUserDetail, ApiClientError, getApiErrorInfo } from "@/lib/api";
import type { ApiErrorInfo } from "@/lib/api";
import { useToast } from "@/components/ui/Toast";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadErrorState } from "@/components/ui/LoadErrorState";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import type { Cafeteria, Order } from "@uniserve/shared-types";

const ORDER_TABS = ["all", "pending", "preparing", "ready", "completed", "cancelled"] as const;
const STAFF_TABS = ["all", "pending", "preparing", "ready"] as const;
/* Phase 58 (Workstream H) — the backend OrderRejectionReason enum
   (orders/models.py) is authoritative; the console offers exactly these
   values. Free text in the reason field previously failed the backend
   enum validator with a 400. */
const ORDER_REJECTION_REASONS: { value: import("@uniserve/shared-types").OrderRejectionReason; label: string }[] = [
  { value: "capacity", label: "Capacity — kitchen at capacity" },
  { value: "item_unavailable", label: "Item unavailable" },
  { value: "cafeteria_issue", label: "Cafeteria issue" },
  { value: "operational_issue", label: "Operational issue" },
  { value: "other", label: "Other" },
];
/* Phase 54 — queue pagination page size (backend limit is capped at 100). */
const PAGE_SIZE = 10;
/* Phase 54 — persist queue filters across reloads (mirrors the Reports console). */
const FILTERS_STORAGE_KEY = "orders-console-filters";

function loadStoredFilters(): { cafeteria?: string; tab?: string; date?: string } | null {
  try {
    const raw = window.sessionStorage.getItem(FILTERS_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export default function OrdersPage() {
  const { user } = useAuth();
  const router = useRouter();
  const isStaff = user?.role === "cafeteria_staff";
  const isManager = user?.role === "cafeteria_manager";
  const isAdmin = user?.role === "university_admin";
  const hasAccess = isStaff || isManager || isAdmin;

  useEffect(() => {
    if (user && !hasAccess) {
      router.push("/dashboard");
    }
  }, [user, hasAccess, router]);

  const [cafeterias, setCafeterias] = useState<Cafeteria[]>([]);
  const [selectedCafeteria, setSelectedCafeteria] = useState<string>("");
  // Default to "all": orders auto-advance (pending → preparing) within
  // seconds of checkout, so a default "pending" tab made freshly placed
  // mobile orders invisible on the dashboard.
  const [activeTab, setActiveTab] = useState<string>("all");
  /* Phase 54 — date filter (backend order_date param; empty = no filter). */
  const [orderDate, setOrderDate] = useState<string>("");
  /* Phase 54 — pagination state. */
  const [page, setPage] = useState<number>(1);
  const [total, setTotal] = useState<number>(0);
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  /* P3-2 / P3-10 — explicit permission state when a scoped order load 403s
     (e.g. a manager selecting a cafeteria they are not assigned to). Must
     never masquerade as "No pending orders". */
  const [accessError, setAccessError] = useState<string | null>(null);
  /* Phase 46 — request-failure states (distinct from the 403 accessError).
     A failed queue load must never masquerade as an empty queue, and a
     failed cafeteria load must never masquerade as an empty selector. */
  const [loadError, setLoadError] = useState<ApiErrorInfo | null>(null);
  const [selectorError, setSelectorError] = useState<ApiErrorInfo | null>(null);
  const [ordersReloadKey, setOrdersReloadKey] = useState(0);
  const { toast } = useToast();

  /* Inline modal state — replaces window.prompt */
  /* Phase 58 (Workstream H) — reject modal: `reason` is now a backend
     `OrderRejectionReason` enum value (validated server-side) with an
     optional free-text note; free text in the reason field previously
     guaranteed a 400 from the enum validator. */
  const [rejectModal, setRejectModal] = useState<{ orderId: string; orderNumber: number; reason: string; notes: string } | null>(null);
  const [delayModal, setDelayModal] = useState<{ orderId: string; minutes: string } | null>(null);
  const [collectModal, setCollectModal] = useState<{ orderId: string; orderNumber: number } | null>(null);
  /* Phase 54 — Manager Cancel Order confirmation (backend rules: manager
     only, assigned cafeteria, pending/preparing statuses; reason optional
     server-side so no reason field is collected). */
  const [cancelModal, setCancelModal] = useState<{ orderId: string; orderNumber: number } | null>(null);
  /* Phase 58 (Workstream E1) — Close Day confirmation (backend: manager-only
     sudden close; cancels PENDING+PREPARING orders, releases inventory,
     sets the cafeteria operational_status CLOSED). Optional notes only. */
  const [closeDayModal, setCloseDayModal] = useState<{ notes: string } | null>(null);
  const [closeDayLoading, setCloseDayLoading] = useState(false);
  /* Phase 54 — Order Details modal (existing GET /orders/{id}; customer name
     resolved via the admin-only user profile endpoint when available). */
  const [detailsModal, setDetailsModal] = useState<{
    orderId: string;
    orderNumber: number;
    detail: any;
    customer: string | null;
    /* Phase 58 (Workstream E3) — live computed ETA from GET /orders/{id}/eta
       (recalculated by the backend; null when unavailable or not fetchable). */
    eta: { eta_minutes: number; pickup_deadline?: string | null } | null;
    loading: boolean;
    error: ApiErrorInfo | null;
  } | null>(null);

  /* Phase 54 — restore persisted queue filters once (reports-console pattern). */
  const filtersRestored = useRef(false);

  const loadCafeterias = useCallback(async () => {
    try {
      // Phase 56 — the orders console is an operational surface: only
      // ACTIVE cafeterias are offered as queue scopes.
      const data = await getCafeterias({ isActive: true });
      // P3-3 — staff/manager selectors default to (and only offer) the
      // cafeterias the user is actually assigned to. Admin keeps the full
      // list. If assignment info is unavailable, fall back to all
      // cafeterias — scoped endpoints still enforce access (see
      // accessError handling in loadOrders).
      let visible = data;
      if (isStaff || isManager) {
        const assigned = await getMyCafeterias();
        if (assigned.length > 0) {
          visible = data.filter((c) => assigned.includes(c.id));
        }
      }
      setCafeterias(visible);
      setSelectorError(null);
      if (!filtersRestored.current) {
        const stored = loadStoredFilters();
        // Home's recent order links include the order's cafeteria. A deep
        // link must take priority over the queue filters kept in sessionStorage,
        // otherwise a Student Cafeteria order looks missing under Faculty Cafe.
        // Only accept cafeteria ids that the current user can actually access.
        const requestedCafeteria = new URLSearchParams(window.location.search).get("cafeteria");
        const linkedCafeteria = visible.find((c) => c.id === requestedCafeteria)?.id;
        if (linkedCafeteria) {
          setSelectedCafeteria(linkedCafeteria);
          setActiveTab("all");
          setOrderDate("");
          setPage(1);
        } else if (stored) {
          const allowedTabs: string[] = isStaff ? [...STAFF_TABS] : [...ORDER_TABS];
          if (typeof stored.tab === "string" && allowedTabs.includes(stored.tab)) {
            setActiveTab(stored.tab);
          }
          if (typeof stored.date === "string" && /^\d{4}-\d{2}-\d{2}$/.test(stored.date)) {
            setOrderDate(stored.date);
          }
          const storedCafeteria = visible.some((c) => c.id === stored.cafeteria)
            ? stored.cafeteria
            : "";
          setSelectedCafeteria((cur) => cur || storedCafeteria || visible[0]?.id || "");
        } else if (visible.length > 0 && !selectedCafeteria) {
          setSelectedCafeteria(visible[0].id);
        }
        filtersRestored.current = true;
      } else if (visible.length > 0 && !selectedCafeteria) {
        setSelectedCafeteria(visible[0].id);
      }
    } catch (err) {
      // Phase 46 — surface the selector load failure (compact error with
      // retry); never render a silently empty cafeteria selector.
      setSelectorError(getApiErrorInfo(err));
      filtersRestored.current = true;
    }
  }, [selectedCafeteria, isStaff, isManager]);

  const loadOrders = useCallback(async (background = false) => {
    if (!selectedCafeteria) return;
    // A 5-second poll must never replace the visible queue with skeletons.
    // Foreground navigation/filter changes still show the loading state.
    if (!background) setLoading(true);
    setAccessError(null);
    setLoadError(null);
    try {
      const data = await getCafeteriaOrders(selectedCafeteria, {
        status: activeTab !== "all" ? activeTab : undefined,
        order_date: orderDate || undefined,
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
      });
      const list = data.orders ?? [];
      const totalCount = typeof data.total === "number" ? data.total : list.length;
      // Phase 54 — handle empty pages: if data changed under the current
      // page (filters/mutations shrank the result set), snap to the last
      // available page instead of showing a phantom empty page.
      if (list.length === 0 && totalCount > 0 && page > 1) {
        const lastPage = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));
        setPage(Math.min(page, lastPage));
        return;
      }
      setOrders(list);
      setTotal(totalCount);
      setDetailsModal((current) => {
        if (!current?.detail) return current;
        const latest = list.find((order) => order.id === current.orderId);
        if (!latest || Date.parse(latest.updated_at) < Date.parse(current.detail.updated_at)) return current;
        return { ...current, detail: { ...current.detail, ...latest },
          customer: latest.customer_name ?? current.customer,
          eta: ["completed", "cancelled"].includes(latest.status) ? null : current.eta };
      });
    } catch (err: any) {
      // P3-2 / P3-10 — a scoped 403 (foreign cafeteria, revoked
      // assignment) surfaces as an explicit access notice, never as a
      // misleading empty queue. Phase 46 — any other failure (5xx, network,
      // timeout) becomes a retryable error state; previously loaded orders
      // stay on screen instead of being replaced by an empty queue.
      if (err instanceof ApiClientError && err.status === 403) {
        setAccessError(
          err.message || "You do not have access to this cafeteria's orders.",
        );
      } else {
        setLoadError(getApiErrorInfo(err));
      }
    } finally {
      if (!background) setLoading(false);
    }
  }, [selectedCafeteria, activeTab, orderDate, page, ordersReloadKey]);

  useEffect(() => { loadCafeterias(); }, [loadCafeterias]);
  useEffect(() => { loadOrders(); }, [loadOrders]);

  // Poll quietly without flashing skeletons or spending requests while
  // the tab is hidden. Navigation, filters, and manual actions still refresh.
  useEffect(() => {
    const interval = setInterval(() => {
      if (!document.hidden) void loadOrders(true);
    }, 5000);
    return () => clearInterval(interval);
  }, [loadOrders]);

  // Phase 54 — persist queue filters across reloads (reports-console pattern)
  useEffect(() => {
    if (!filtersRestored.current) return; // do not clobber storage pre-restore
    try {
      window.sessionStorage.setItem(
        FILTERS_STORAGE_KEY,
        JSON.stringify({ cafeteria: selectedCafeteria, tab: activeTab, date: orderDate }),
      );
    } catch {
      /* storage unavailable — filters simply do not persist */
    }
  }, [selectedCafeteria, activeTab, orderDate]);

  const handleAction = async (orderId: string, action: () => Promise<any>) => {
    setActionLoading(orderId);
    try {
      await action();
      await loadOrders();
      if (detailsModal?.orderId === orderId) await reloadDetails(orderId);
    } catch (err: any) {
      toast(err?.message ?? "Action failed", "error");
    } finally {
      setActionLoading(null);
    }
  };

  // Order Details modal actions — same transitions as the queue cards, but
  // also refresh the open modal so the status badge and timestamps update
  // without closing and reopening the dialog.
  const handleModalAction = async (orderId: string, action: () => Promise<any>) => {
    setActionLoading(orderId);
    try {
      await action();
      await loadOrders();
      await reloadDetails(orderId);
    } catch (err: any) {
      toast(err?.message ?? "Action failed", "error");
      await loadOrders();
    } finally {
      setActionLoading(null);
    }
  };

  // Collect is terminal — backend is authoritative for collectability
  // (ready state, cafeteria assignment, already-collected conflicts).
  // Surface the server message and refresh on success AND error so the
  // queue always reflects the real order state.
  const handleCollect = async (orderId: string, orderNumber: number) => {
    setActionLoading(orderId);
    try {
      await collectOrder({ order_number: orderNumber });
      setCollectModal(null);
      toast(`Order #${orderNumber} collected`, "success");
      await loadOrders();
      if (detailsModal?.orderId === orderId) await reloadDetails(orderId);
    } catch (err: any) {
      toast(err?.message ?? "Collect failed", "error");
      setCollectModal(null);
      await loadOrders();
    } finally {
      setActionLoading(null);
    }
  };

  // Phase 54 — Manager Cancel Order. The backend enforces the real rules
  // (manager role, cafeteria assignment, pending/preparing statuses);
  // surface server messages verbatim, refresh on success AND error.
  const handleManagerCancel = async (orderId: string, orderNumber: number) => {
    setActionLoading(orderId);
    try {
      await managerCancelOrder(orderId);
      setCancelModal(null);
      toast(`Order #${orderNumber} cancelled`, "success");
      await loadOrders();
      if (detailsModal?.orderId === orderId) await reloadDetails(orderId);
    } catch (err: any) {
      toast(err?.message ?? "Cancel failed", "error");
      setCancelModal(null);
      await loadOrders();
    } finally {
      setActionLoading(null);
    }
  };

  // Phase 58 (Workstream E1) — Close Day. Backend rules are enforced
  // server-side (manager only, assigned cafeteria); the response lists the
  // cancelled orders (total = 0 means nothing was open). Surface backend
  // messages verbatim and refresh the queue afterwards.
  const handleCloseDay = async () => {
    if (!selectedCafeteria) return;
    setCloseDayLoading(true);
    try {
      const res = await closeCafeteriaDay(
        selectedCafeteria,
        closeDayModal?.notes.trim() || undefined,
      );
      const n = typeof res.total === "number" ? res.total : (res.orders?.length ?? 0);
      setCloseDayModal(null);
      toast(
        n > 0
          ? `${cafeteriaLabel} closed — ${n} open order${n === 1 ? "" : "s"} cancelled`
          : `${cafeteriaLabel} closed — no open orders to cancel`,
        "success",
      );
      await loadOrders();
    } catch (err: any) {
      toast(err?.message ?? "Close day failed", "error");
    } finally {
      setCloseDayLoading(false);
    }
  };

  // Phase 54 — Order Details: load the existing detail endpoint. The admin
  // additionally resolves the customer name via the admin-only user
  // profile endpoint; other roles honestly fall back to the customer id.
  const reloadDetails = useCallback(async (orderId: string) => {
    try {
      const detail = await getOrderDetail(orderId);
      let customer: string | null = detail.customer_name ?? null;
      if (isAdmin && !customer) {
        try {
          const u = await getUserDetail(detail.user_id);
          customer = `${u.first_name} ${u.last_name} (${u.university_email})`;
        } catch {
          customer = null; // profile unavailable — fall back to user id
        }
      }
      // Phase 58 (Workstream E3) — for still-open orders fetch the live
      // computed ETA (owner/admin/assigned manager/staff authorized
      // server-side). A failed ETA fetch never blocks the details modal.
      let eta: { eta_minutes: number; pickup_deadline?: string | null } | null = null;
      if (detail && ["pending", "preparing", "ready"].includes(detail.status)) {
        try {
          eta = await getOrderEta(orderId);
        } catch {
          eta = null;
        }
      }
      setDetailsModal((m) =>
        m && m.orderId === orderId && (!m.detail || Date.parse(detail.updated_at) >= Date.parse(m.detail.updated_at))
          ? { ...m, detail, customer, eta, loading: false, error: null } : m,
      );
    } catch (err) {
      setDetailsModal((m) =>
        m && m.orderId === orderId ? { ...m, loading: false, error: getApiErrorInfo(err) } : m,
      );
    }
  }, [isAdmin]);

  useEffect(() => {
    if (!detailsModal?.orderId) return;
    const orderId = detailsModal.orderId;
    const interval = setInterval(() => {
      if (!document.hidden) void reloadDetails(orderId);
    }, 5000);
    return () => clearInterval(interval);
  }, [detailsModal?.orderId, reloadDetails]);

  const handleOpenDetails = (orderId: string, orderNumber: number) => {
    setDetailsModal({ orderId, orderNumber, detail: null, customer: null, eta: null, loading: true, error: null });
    void reloadDetails(orderId);
  };

  const formatDate = (iso: string) => {
    if (!iso) return "";
    // Time-only string like "18:18"
    if (/^\d{1,2}:\d{2}$/.test(iso)) {
      const [h, m] = iso.split(":").map(Number);
      const ampm = h >= 12 ? "PM" : "AM";
      const h12 = h % 12 || 12;
      return `${h12}:${String(m).padStart(2, "0")} ${ampm}`;
    }
    // Date-only string like "2026-09-30" — format as date without timezone conversion
    if (/^\d{4}-\d{2}-\d{2}$/.test(iso)) {
      const [y, mo, d] = iso.split("-").map(Number);
      return new Date(y, mo - 1, d).toLocaleString("en-US", {
        month: "short", day: "numeric",
      });
    }
    try {
      return new Date(iso).toLocaleString("en-US", {
        month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
      });
    } catch { return iso; }
  };

  const formatCurrency = (amount: number) => `PKR ${Math.round(amount / 100)}`;

  const tabs = isStaff ? [...STAFF_TABS] : [...ORDER_TABS];
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const cafeteriaLabel = cafeterias.find((c) => c.id === selectedCafeteria)?.name ?? "Selected cafeteria";
  const canManagerCancel = (status: string) => status === "pending" || status === "preparing";

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Order Queue"
        description={isStaff ? "View and process incoming orders" : isManager ? "Manage order operations" : "University-wide order overview"}
        actions={
          <div className="flex items-center gap-2 flex-wrap">
            <select
              value={selectedCafeteria}
              onChange={(e) => { setSelectedCafeteria(e.target.value); setPage(1); }}
              className="px-3 py-2 text-sm border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)]"
            >
              {cafeterias.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
            {/* Phase 54 — date filter wired to the backend order_date param */}
            <input
              type="date"
              value={orderDate}
              onChange={(e) => { setOrderDate(e.target.value); setPage(1); }}
              aria-label="Filter by order date"
              className="px-2 py-2 text-sm border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)]"
            />
            {/* Phase 58 (Workstream E1) — Close Day: manager-only sudden close
                of the currently selected cafeteria (backend RBAC: manager,
                assigned cafeteria — enforced server-side). */}
            {isManager && selectedCafeteria && (
              <Button
                size="sm"
                variant="danger"
                onClick={() => setCloseDayModal({ notes: "" })}
              >
                Close Day
              </Button>
            )}
          </div>
        }
      />

      {/* The staff queue is the operational counterpart of the student app:
          each action writes through the API and is visible in mobile order tracking.
          The embedded SHA helps detect old immutable Vercel deployment links. */}
      <div role="note" className="mb-5 flex flex-col gap-2 rounded-xl border border-[var(--border-default)] bg-[var(--bg-secondary)] px-4 py-3 text-sm text-[var(--text-secondary)] sm:flex-row sm:items-center sm:justify-between">
        <p>
          <span className="font-semibold text-[var(--text-primary)]">Order workflow:</span>{" "}
          Pending → Confirm → Prepare → Ready for pickup → Collected.
          {" "}Choose the correct cafeteria and status, then use the action on each order card.
        </p>
        <p className="shrink-0 text-xs text-[var(--text-muted)]" title="Web build revision; compare with the deployed GitHub commit">
          Web build: {(process.env.UNISERVE_BUILD_SHA || "local").slice(0, 8)}
        </p>
      </div>

      {/* Phase 46 — cafeteria selector load failure (compact, retryable) */}
      {selectorError && (
        <LoadErrorState
          compact
          error={selectorError}
          subject="cafeterias"
          onRetry={() => loadCafeterias()}
          className="mb-4 border border-red-200 dark:border-red-800 bg-red-50/50 dark:bg-red-900/10 rounded-xl"
        />
      )}

      {/* Status tabs */}
      <div className="flex gap-1 mb-6 border-b border-[var(--border-default)] overflow-x-auto">
        {tabs.map((tab) => (
          <button
            key={tab}
            onClick={() => { setActiveTab(tab); setPage(1); }}
            className={`px-4 py-2.5 text-sm font-medium capitalize transition-colors border-b-2 whitespace-nowrap ${
              activeTab === tab
                ? "border-brand-600 text-brand-700 dark:text-brand-400"
                : "border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)]"
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Phase 54 — active date-filter indicator with an easy clear action */}
      {orderDate && (
        <div className="flex items-center gap-2 mb-4 text-xs">
          <span className="px-2 py-1 rounded-lg bg-brand-50 dark:bg-brand-900/20 text-brand-700 dark:text-brand-300 border border-brand-200 dark:border-brand-800 font-medium">
            Date filter: {formatDate(orderDate)}
          </span>
          <button
            onClick={() => { setOrderDate(""); setPage(1); }}
            className="text-[var(--text-muted)] hover:text-[var(--text-primary)] underline underline-offset-2"
          >
            Clear date filter
          </button>
        </div>
      )}

      {/* Orders list — P3-2/P3-10: a scoped 403 renders an explicit access
          notice, never a misleading "No pending orders" empty state. */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-24 bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl skeleton" />
          ))}
        </div>
      ) : accessError ? (
        <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl p-6 text-center">
          <div className="mx-auto mb-3 w-10 h-10 flex items-center justify-center rounded-full bg-amber-100 dark:bg-amber-900/40">
            <svg className="w-5 h-5 text-amber-600 dark:text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <p className="text-sm font-semibold text-amber-800 dark:text-amber-300">
            You don&apos;t have access to this cafeteria&apos;s orders
          </p>
          <p className="text-xs text-amber-700 dark:text-amber-400 mt-1 max-w-md mx-auto">
            {accessError}
          </p>
          <p className="text-xs text-amber-700 dark:text-amber-400 mt-2">
            Your staff / manager assignment determines which cafeteria queues you can manage.
          </p>
        </div>
      ) : loadError && orders.length === 0 ? (
        <LoadErrorState
          error={loadError}
          subject={`orders in the ${activeTab} queue`}
          onRetry={() => setOrdersReloadKey((k) => k + 1)}
        />
      ) : orders.length === 0 ? (
        <EmptyState
          title={
            activeTab === "all"
              ? "No orders yet"
              : orderDate
              ? `No ${activeTab} orders on ${formatDate(orderDate)}`
              : `No ${activeTab} orders`
          }
          description={
            orderDate
              ? `No ${activeTab} orders match this date for ${cafeteriaLabel}. Clear the date filter to see more orders.`
              : activeTab === "all"
              ? "Orders from the mobile app and web will appear here in real time."
              : "Orders matching this filter will appear here."
          }
          icon={
            <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
          }
        />
      ) : (
        <div className="space-y-3">
          {loadError && (
            <LoadErrorState
              compact
              error={loadError}
              subject="orders"
              onRetry={() => setOrdersReloadKey((k) => k + 1)}
              className="border border-red-200 dark:border-red-800 bg-red-50/50 dark:bg-red-900/10 rounded-xl"
            />
          )}
          {orders.map((order) => (
            <div
              key={order.id}
              className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl p-4 shadow-card hover:shadow-card-hover transition-shadow"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-bold text-[var(--text-primary)]">
                      #{order.order_number}
                    </span>
                    <StatusBadge status={order.status} />
                    <span className="text-xs text-[var(--text-muted)] capitalize">
                      {order.order_type} · {order.payment_method}
                    </span>
                  </div>

                  {/* Items */}
                  <div className="text-sm text-[var(--text-secondary)] mb-1">
                    {order.items?.map((item: any) => `${item.quantity}× ${item.item_name}`).join(", ")}
                  </div>

                  <div className="flex items-center gap-3 text-xs text-[var(--text-muted)]">
                    <span>{formatDate(order.order_date)}</span>
                    <span className="font-medium text-[var(--text-primary)]">{formatCurrency(order.total_amount)}</span>
                    {order.note && <span className="italic">&quot;{order.note}&quot;</span>}
                    {order.scheduled_collection_time && (
                      <span className="text-brand-600">Scheduled: {formatDate(order.scheduled_collection_time)}</span>
                    )}
                  </div>
                </div>

                {/* Actions */}
                <div className="flex gap-2 flex-shrink-0 flex-wrap justify-end">
                  {/* Phase 54 — Order Details (all console roles; the backend
                      detail endpoint enforces per-order authorization). */}
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => handleOpenDetails(order.id, order.order_number)}
                  >
                    Details
                  </Button>
                  {(isStaff || isManager || isAdmin) && (
                    <>
                      {order.status === "pending" && (isManager || isStaff || isAdmin) && (
                        <>
                          {!order.confirmed_at && (
                            <Button
                              size="sm"
                              variant="primary"
                              loading={actionLoading === order.id}
                              onClick={() => handleAction(order.id, () => confirmOrder(order.id))}
                            >
                              Confirm
                            </Button>
                          )}
                          {isManager && (
                            <Button
                              size="sm"
                              variant="danger"
                              loading={actionLoading === order.id}
                              onClick={() => setRejectModal({ orderId: order.id, orderNumber: order.order_number, reason: "", notes: "" })}
                            >
                              Reject
                            </Button>
                          )}
                        </>
                      )}
                      {/* F-ACC-06 — Prepare is only valid once the order has
                          been confirmed (backend rejects prepare on an
                          unconfirmed pending order with 400). Mirror the
                          Confirm gate above so the console never offers an
                          action the server will refuse. */}
                      {order.status === "pending" && !!order.confirmed_at && (
                        <Button
                          size="sm"
                          variant="secondary"
                          loading={actionLoading === order.id}
                          onClick={() => handleAction(order.id, () => prepareOrder(order.id))}
                        >
                          Prepare
                        </Button>
                      )}
                      {order.status === "preparing" && (
                        <Button
                          size="sm"
                          variant="primary"
                          loading={actionLoading === order.id}
                          onClick={() => handleAction(order.id, () => readyOrder(order.id))}
                        >
                          Ready
                        </Button>
                      )}
                      {order.status === "ready" && (
                        <Button
                          size="sm"
                          variant="primary"
                          loading={actionLoading === order.id}
                          onClick={() => setCollectModal({ orderId: order.id, orderNumber: order.order_number })}
                        >
                          Collect
                        </Button>
                      )}
                      {/* P3-9: delay control mirrors backend rules — manager or
                          staff on PREPARING/READY orders (PUT /orders/{id}/delay). */}
                      {(order.status === "preparing" || order.status === "ready") && (isManager || isStaff || isAdmin) && (
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => setDelayModal({ orderId: order.id, minutes: "" })}
                        >
                          Delay
                        </Button>
                      )}
                    </>
                  )}
                  {/* Phase 54 — Manager Cancel Order: shown only where the
                      backend rules permit (manager + pending/preparing). Never
                      shown to staff, students, or admin — backend RBAC rejects
                      those roles with 403. */}
                  {isManager && canManagerCancel(order.status) && (
                    <Button
                      size="sm"
                      variant="danger"
                      loading={actionLoading === order.id}
                      onClick={() => setCancelModal({ orderId: order.id, orderNumber: order.order_number })}
                    >
                      Cancel
                    </Button>
                  )}
                </div>
              </div>
            </div>
          ))}

          {/* Phase 54 — pagination footer (backend limit/offset; filters
              preserved across pages because loadOrders reads all filter state) */}
          {total > 0 && (
            <div className="flex items-center justify-between pt-2 text-sm">
              <p className="text-xs text-[var(--text-muted)]">
                Showing {Math.min((page - 1) * PAGE_SIZE + 1, total)}–{Math.min(page * PAGE_SIZE, total)} of {total} orders · Page {page} of {totalPages}
              </p>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={page <= 1 || loading}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  Previous
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={page >= totalPages || loading}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ─── Phase 58 (Workstream E1) — Close Day confirmation modal ─── */}
      {closeDayModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setCloseDayModal(null)}>
          <div
            className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl shadow-xl w-full max-w-md mx-4 p-6 max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-base font-semibold text-[var(--text-primary)] mb-3">
              Close Day — {cafeteriaLabel}
            </h3>
            <p className="text-sm text-[var(--text-secondary)] mb-2">
              Closing the day <span className="font-bold text-red-600 dark:text-red-400">cancels every
              pending and preparing order</span> for {cafeteriaLabel}, releases their reserved
              inventory, and sets the cafeteria to CLOSED. Affected customers are notified.
            </p>
            <p className="text-xs text-[var(--text-muted)] mb-4">
              Ready and completed orders are unaffected. The backend rejects this action unless you
              are a manager assigned to this cafeteria.
            </p>
            <label className="block text-sm text-[var(--text-secondary)] mb-1">
              Notes (optional)
            </label>
            <textarea
              value={closeDayModal.notes}
              onChange={(e) => setCloseDayModal({ notes: e.target.value.slice(0, 500) })}
              className="w-full px-3 py-2 text-sm border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)]"
              rows={3}
              placeholder="Reason for closing (max 500 characters)..."
            />
            <div className="flex justify-end gap-2 mt-4">
              <Button size="sm" variant="ghost" onClick={() => setCloseDayModal(null)}>
                Keep Open
              </Button>
              <Button
                size="sm"
                variant="danger"
                loading={closeDayLoading}
                disabled={closeDayLoading}
                onClick={handleCloseDay}
              >
                Close Day
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ─── Phase 54 — Manager Cancel Order confirmation modal ─── */}
      {cancelModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setCancelModal(null)}>
          <div
            className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl shadow-xl w-full max-w-sm mx-4 p-6 max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-base font-semibold text-[var(--text-primary)] mb-3">Cancel Order</h3>
            <p className="text-sm text-[var(--text-secondary)] mb-2">
              Cancel order{" "}
              <span className="font-bold text-[var(--text-primary)]">#{cancelModal.orderNumber}</span>?
              This marks the order as cancelled and notifies the customer. Any reserved
              inventory is released.
            </p>
            <p className="text-xs text-[var(--text-muted)] mb-4">
              Only pending or preparing orders can be cancelled by a manager.
            </p>
            <div className="flex justify-end gap-2">
              <Button size="sm" variant="ghost" onClick={() => setCancelModal(null)}>Keep Order</Button>
              <Button
                size="sm"
                variant="danger"
                loading={actionLoading === cancelModal.orderId}
                onClick={() => handleManagerCancel(cancelModal.orderId, cancelModal.orderNumber)}
              >
                Cancel Order
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ─── Phase 54 — Order Details modal ─── */}
      {detailsModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setDetailsModal(null)}>
          <div
            role="dialog"
            aria-modal="true"
            aria-label={`Order #${detailsModal.orderNumber}`}
            className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl shadow-xl w-full max-w-lg mx-4 p-6 max-h-[85vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-semibold text-[var(--text-primary)]">
                Order #{detailsModal.orderNumber}
              </h3>
              {detailsModal.detail && <StatusBadge status={detailsModal.detail.status} />}
            </div>

            {detailsModal.loading ? (
              <div className="py-10 flex flex-col items-center gap-3 text-[var(--text-muted)]">
                <Spinner />
                <p className="text-sm">Loading order details…</p>
              </div>
            ) : detailsModal.error ? (
              <LoadErrorState
                error={detailsModal.error}
                subject="order details"
                onRetry={() => reloadDetails(detailsModal.orderId)}
              />
            ) : detailsModal.detail ? (
              <div className="space-y-4 text-sm">
                <div className="grid grid-cols-2 gap-x-4 gap-y-2">
                  <div>
                    <p className="text-xs text-[var(--text-muted)]">Customer</p>
                    <p className="text-[var(--text-primary)] break-words">
                      {detailsModal.customer ?? (
                        <span title={detailsModal.detail.user_id}>
                          Customer name unavailable
                        </span>
                      )}
                    </p>
                    {!detailsModal.customer && isAdmin && (
                      <p className="text-xs text-amber-700 dark:text-amber-400">
                        Profile unavailable — showing customer id.
                      </p>
                    )}
                  </div>
                  <div>
                    <p className="text-xs text-[var(--text-muted)]">Cafeteria</p>
                    <p className="text-[var(--text-primary)]">
                      {cafeterias.find((c) => c.id === detailsModal.detail.cafeteria_id)?.name ??
                        detailsModal.detail.cafeteria_id}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-[var(--text-muted)]">Order type</p>
                    <p className="text-[var(--text-primary)] capitalize">
                      {detailsModal.detail.order_type}
                      {detailsModal.detail.scheduled_collection_time
                        ? ` · scheduled ${formatDate(detailsModal.detail.scheduled_collection_time)}`
                        : ""}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-[var(--text-muted)]">Payment</p>
                    <p className="text-[var(--text-primary)] capitalize">
                      {detailsModal.detail.payment_method}
                      {detailsModal.detail.collection_method
                        ? ` · ${detailsModal.detail.collection_method}`
                        : ""}
                    </p>
                  </div>
                </div>

                {/* Items */}
                <div>
                  <p className="text-xs text-[var(--text-muted)] mb-1">Items</p>
                  <div className="border border-[var(--border-default)] rounded-lg divide-y divide-[var(--border-default)]">
                    {detailsModal.detail.items?.map((item: any) => (
                      <div key={item.id} className="flex items-center justify-between px-3 py-2 text-xs">
                        <span className="text-[var(--text-primary)]">
                          {item.quantity}× {item.item_name}
                        </span>
                        <span className="text-[var(--text-secondary)]">
                          {formatCurrency(item.unit_price)} each · {formatCurrency(item.subtotal)}
                        </span>
                      </div>
                    ))}
                    <div className="flex items-center justify-between px-3 py-2 text-xs font-semibold bg-[var(--bg-secondary)] rounded-b-lg">
                      <span className="text-[var(--text-primary)]">Total</span>
                      <span className="text-[var(--text-primary)]">
                        {formatCurrency(detailsModal.detail.total_amount)}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Timestamps & context */}
                <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
                  <div>
                    <span className="text-[var(--text-muted)]">Placed: </span>
                    <span className="text-[var(--text-primary)]">{formatDate(detailsModal.detail.created_at)}</span>
                  </div>
                  {detailsModal.detail.confirmed_at && (
                    <div>
                      <span className="text-[var(--text-muted)]">Confirmed: </span>
                      <span className="text-[var(--text-primary)]">{formatDate(detailsModal.detail.confirmed_at)}</span>
                    </div>
                  )}
                  {detailsModal.detail.preparation_started_at && (
                    <div>
                      <span className="text-[var(--text-muted)]">Preparing since: </span>
                      <span className="text-[var(--text-primary)]">{formatDate(detailsModal.detail.preparation_started_at)}</span>
                    </div>
                  )}
                  {detailsModal.detail.ready_at && (
                    <div>
                      <span className="text-[var(--text-muted)]">Ready at: </span>
                      <span className="text-[var(--text-primary)]">{formatDate(detailsModal.detail.ready_at)}</span>
                    </div>
                  )}
                  {detailsModal.detail.pickup_deadline && (
                    <div>
                      <span className="text-[var(--text-muted)]">Pickup deadline: </span>
                      <span className="text-[var(--text-primary)]">{formatDate(detailsModal.detail.pickup_deadline)}</span>
                    </div>
                  )}
                  {detailsModal.detail.eta_minutes != null && (
                    <div>
                      <span className="text-[var(--text-muted)]">ETA: </span>
                      <span className="text-[var(--text-primary)]">{detailsModal.detail.eta_minutes} min</span>
                    </div>
                  )}
                  {detailsModal.eta != null && (
                    <div className="col-span-2 mt-1 px-2.5 py-2 rounded-lg bg-brand-50 dark:bg-brand-900/20 border border-brand-200 dark:border-brand-800">
                      <span className="text-[var(--text-muted)]">Computed ETA: </span>
                      <span className="font-semibold text-[var(--text-primary)]">
                        {detailsModal.eta.eta_minutes} min
                      </span>
                      {detailsModal.eta.pickup_deadline && (
                        <span className="text-[var(--text-secondary)]">
                          {" "}· pickup deadline {formatDate(detailsModal.eta.pickup_deadline)}
                        </span>
                      )}
                      <p className="text-[10px] text-[var(--text-muted)] mt-0.5">
                        Estimated pickup time based on current queue.
                      </p>
                    </div>
                  )}
                  {detailsModal.detail.collected_at && (
                    <div>
                      <span className="text-[var(--text-muted)]">Collected: </span>
                      <span className="text-[var(--text-primary)]">{formatDate(detailsModal.detail.collected_at)}</span>
                    </div>
                  )}
                  {detailsModal.detail.cancelled_at && (
                    <div>
                      <span className="text-[var(--text-muted)]">Cancelled: </span>
                      <span className="text-[var(--text-primary)]">{formatDate(detailsModal.detail.cancelled_at)}</span>
                    </div>
                  )}
                  {detailsModal.detail.rejection_reason && (
                    <div className="col-span-2">
                      <span className="text-[var(--text-muted)]">Rejection reason: </span>
                      <span className="text-[var(--text-primary)]">
                        {ORDER_REJECTION_REASONS.find((r) => r.value === detailsModal.detail.rejection_reason)?.label ?? detailsModal.detail.rejection_reason}
                      </span>
                      {detailsModal.detail.rejection_note && (
                        <span className="text-[var(--text-secondary)]"> — {detailsModal.detail.rejection_note}</span>
                      )}
                    </div>
                  )}
                  {detailsModal.detail.cancellation_reason && (
                    <div className="col-span-2">
                      <span className="text-[var(--text-muted)]">Cancellation reason: </span>
                      <span className="text-[var(--text-primary)]">{detailsModal.detail.cancellation_reason}</span>
                    </div>
                  )}
                </div>

                {(detailsModal.detail.note || detailsModal.detail.collection_token) && (
                  <div className="space-y-1.5 text-xs">
                    {detailsModal.detail.note && (
                      <p className="text-[var(--text-secondary)] italic">&quot;{detailsModal.detail.note}&quot;</p>
                    )}
                    {detailsModal.detail.collection_token && (
                      <p className="text-[var(--text-muted)]">
                        Collection token:{" "}
                        <span className="font-mono text-[var(--text-secondary)]" title="Full token hidden for security">
                          {String(detailsModal.detail.collection_token).slice(0, 8)}…
                        </span>
                      </p>
                    )}
                  </div>
                )}
              </div>
            ) : null}

            {detailsModal.detail?.status === "preparing" && (isAdmin || isManager || isStaff) && (
              <p role="status" className="mt-4 rounded-lg border border-brand-200 bg-brand-50 px-3 py-2 text-sm text-brand-800 dark:border-brand-800 dark:bg-brand-900/20 dark:text-brand-300">
                Kitchen is preparing this order. When the food is ready, select{" "}
                <strong>Ready</strong> below to notify the student that pickup is available.
              </p>
            )}

            <div className="flex flex-wrap justify-end gap-2 mt-5">
              {detailsModal.detail && (isStaff || isManager || isAdmin) && (
                <>
                  {detailsModal.detail.status === "pending" && (
                    <>
                      {!detailsModal.detail.confirmed_at && (
                        <Button
                          size="sm"
                          variant="primary"
                          loading={actionLoading === detailsModal.orderId}
                          onClick={() => handleModalAction(detailsModal.orderId, () => confirmOrder(detailsModal.orderId))}
                        >
                          Confirm
                        </Button>
                      )}
                      {isManager && (
                        <Button
                          size="sm"
                          variant="danger"
                          loading={actionLoading === detailsModal.orderId}
                          onClick={() => setRejectModal({ orderId: detailsModal.orderId, orderNumber: detailsModal.orderNumber, reason: "", notes: "" })}
                        >
                          Reject
                        </Button>
                      )}
                    </>
                  )}
                  {detailsModal.detail.status === "pending" && !!detailsModal.detail.confirmed_at && (
                    <Button
                      size="sm"
                      variant="secondary"
                      loading={actionLoading === detailsModal.orderId}
                      onClick={() => handleModalAction(detailsModal.orderId, () => prepareOrder(detailsModal.orderId))}
                    >
                      Prepare
                    </Button>
                  )}
                  {detailsModal.detail.status === "preparing" && (
                    <Button
                      size="sm"
                      variant="primary"
                      loading={actionLoading === detailsModal.orderId}
                      onClick={() => handleModalAction(detailsModal.orderId, () => readyOrder(detailsModal.orderId))}
                    >
                      Ready
                    </Button>
                  )}
                  {detailsModal.detail.status === "ready" && (
                    <Button
                      size="sm"
                      variant="primary"
                      loading={actionLoading === detailsModal.orderId}
                      onClick={() => setCollectModal({ orderId: detailsModal.orderId, orderNumber: detailsModal.orderNumber })}
                    >
                      Collect
                    </Button>
                  )}
                  {(detailsModal.detail.status === "preparing" || detailsModal.detail.status === "ready") && (
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => setDelayModal({ orderId: detailsModal.orderId, minutes: "" })}
                    >
                      Delay
                    </Button>
                  )}
                </>
              )}
              {detailsModal.detail && isManager && canManagerCancel(detailsModal.detail.status) && (
                <Button
                  size="sm"
                  variant="danger"
                  loading={actionLoading === detailsModal.orderId}
                  onClick={() => setCancelModal({ orderId: detailsModal.orderId, orderNumber: detailsModal.orderNumber })}
                >
                  Cancel
                </Button>
              )}
              <Button size="sm" variant="ghost" onClick={() => setDetailsModal(null)}>Close</Button>
            </div>
          </div>
        </div>
      )}

      {/* ─── Reject order modal ─── */}
      {rejectModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setRejectModal(null)}>
          <div
            className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl shadow-xl w-full max-w-sm mx-4 p-6 max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-base font-semibold text-[var(--text-primary)] mb-3">
              Reject Order #{rejectModal.orderNumber}
            </h3>
            <label className="block text-sm text-[var(--text-secondary)] mb-1">Reason</label>
            <select
              value={rejectModal.reason}
              onChange={(e) => setRejectModal({ ...rejectModal, reason: e.target.value })}
              className="w-full px-3 py-2 text-sm border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)]"
              autoFocus
            >
              <option value="">Select a reason…</option>
              {ORDER_REJECTION_REASONS.map((r) => (
                <option key={r.value} value={r.value}>{r.label}</option>
              ))}
            </select>
            <p className="text-xs text-[var(--text-muted)] mt-1">
              Reason values match the backend contract (capacity, item_unavailable,
              cafeteria_issue, operational_issue, other).
            </p>
            <label className="block text-sm text-[var(--text-secondary)] mt-3 mb-1">
              Note (optional)
            </label>
            <textarea
              value={rejectModal.notes}
              onChange={(e) => setRejectModal({ ...rejectModal, notes: e.target.value.slice(0, 500) })}
              className="w-full px-3 py-2 text-sm border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)]"
              rows={3}
              placeholder="Additional detail for the customer (max 500 characters)…"
            />
            <div className="flex justify-end gap-2 mt-4">
              <Button size="sm" variant="ghost" onClick={() => setRejectModal(null)}>Cancel</Button>
              <Button
                size="sm"
                variant="danger"
                loading={actionLoading === rejectModal.orderId}
                onClick={() => {
                  if (!rejectModal.reason) return;
                  handleAction(rejectModal.orderId, () =>
                    rejectOrder(rejectModal.orderId, rejectModal.reason, rejectModal.notes || undefined),
                  );
                  setRejectModal(null);
                }}
              >
                Confirm Reject
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ─── Collect order modal ─── */}
      {collectModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setCollectModal(null)}>
          <div
            className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl shadow-xl w-full max-w-sm mx-4 p-6 max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-base font-semibold text-[var(--text-primary)] mb-3">Collect Order</h3>
            <p className="text-sm text-[var(--text-secondary)] mb-4">
              Confirm that order{" "}
              <span className="font-bold text-[var(--text-primary)]">#{collectModal.orderNumber}</span>{" "}
              has been handed to the customer. The order will be marked as completed.
            </p>
            <div className="flex justify-end gap-2">
              <Button size="sm" variant="ghost" onClick={() => setCollectModal(null)}>Cancel</Button>
              <Button
                size="sm"
                variant="primary"
                loading={actionLoading === collectModal.orderId}
                onClick={() => handleCollect(collectModal.orderId, collectModal.orderNumber)}
              >
                Confirm Collect
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ─── Delay order modal ─── */}
      {delayModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setDelayModal(null)}>
          <div
            className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl shadow-xl w-full max-w-sm mx-4 p-6 max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-base font-semibold text-[var(--text-primary)] mb-3">Delay Order</h3>
            <label className="block text-sm text-[var(--text-secondary)] mb-1">Additional minutes</label>
            <input
              type="number"
              min={1}
              max={120}
              value={delayModal.minutes}
              onChange={(e) => setDelayModal({ ...delayModal, minutes: e.target.value })}
              className="w-full px-3 py-2 text-sm border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)]"
              placeholder="e.g. 15"
              autoFocus
            />
            <p className="text-xs text-[var(--text-muted)] mt-1">1–120 minutes. ETA and pickup deadline are extended; the customer is notified.</p>
            <div className="flex justify-end gap-2 mt-4">
              <Button size="sm" variant="ghost" onClick={() => setDelayModal(null)}>Cancel</Button>
              <Button
                size="sm"
                variant="secondary"
                loading={actionLoading === delayModal.orderId}
                onClick={() => {
                  const mins = parseInt(delayModal.minutes);
                  if (!mins || mins < 1 || mins > 120) return;
                  handleAction(delayModal.orderId, () => delayOrder(delayModal.orderId, mins));
                  setDelayModal(null);
                }}
              >
                Confirm Delay
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
