"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import { getCafeterias, getCafeteriaOrders, confirmOrder, prepareOrder, readyOrder, delayOrder, rejectOrder } from "@/lib/api";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { EmptyState } from "@/components/ui/EmptyState";
import { Button } from "@/components/ui/Button";
import type { Cafeteria, Order } from "@uniserve/shared-types";

const ORDER_TABS = ["pending", "preparing", "ready", "completed", "cancelled"] as const;

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
  const [activeTab, setActiveTab] = useState<string>("pending");
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const loadCafeterias = useCallback(async () => {
    try {
      const data = await getCafeterias();
      setCafeterias(data);
      if (data.length > 0 && !selectedCafeteria) {
        setSelectedCafeteria(data[0].id);
      }
    } catch {}
  }, [selectedCafeteria]);

  const loadOrders = useCallback(async () => {
    if (!selectedCafeteria) return;
    setLoading(true);
    try {
      const data = await getCafeteriaOrders(selectedCafeteria, {
        status: activeTab !== "all" ? activeTab : undefined,
      });
      setOrders(data.orders ?? []);
    } catch {
      setOrders([]);
    } finally {
      setLoading(false);
    }
  }, [selectedCafeteria, activeTab]);

  useEffect(() => { loadCafeterias(); }, [loadCafeterias]);
  useEffect(() => { loadOrders(); }, [loadOrders]);

  // Auto-refresh every 30s
  useEffect(() => {
    const interval = setInterval(loadOrders, 30000);
    return () => clearInterval(interval);
  }, [loadOrders]);

  const handleAction = async (orderId: string, action: () => Promise<any>) => {
    setActionLoading(orderId);
    try {
      await action();
      await loadOrders();
    } catch (err: any) {
      alert(err?.message ?? "Action failed");
    } finally {
      setActionLoading(null);
    }
  };

  const formatDate = (iso: string) => {
    try {
      return new Date(iso).toLocaleString("en-US", {
        month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
      });
    } catch { return iso; }
  };

  const formatCurrency = (amount: number) => `PKR ${Math.round(amount / 100)}`;

  const tabs = isStaff ? ["pending", "preparing", "ready"] : ORDER_TABS;

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Order Queue"
        description={isStaff ? "View and process incoming orders" : isManager ? "Manage order operations" : "University-wide order overview"}
        actions={
          <div className="flex items-center gap-2">
            <select
              value={selectedCafeteria}
              onChange={(e) => setSelectedCafeteria(e.target.value)}
              className="px-3 py-2 text-sm border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)]"
            >
              {cafeterias.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>
        }
      />

      {/* Status tabs */}
      <div className="flex gap-1 mb-6 border-b border-[var(--border-default)] overflow-x-auto">
        {tabs.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
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

      {/* Orders list */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-24 bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl skeleton" />
          ))}
        </div>
      ) : orders.length === 0 ? (
        <EmptyState
          title={`No ${activeTab} orders`}
          description="Orders matching this filter will appear here."
          icon={
            <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
          }
        />
      ) : (
        <div className="space-y-3">
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
                    {order.note && <span className="italic">"{order.note}"</span>}
                    {order.scheduled_collection_time && (
                      <span className="text-brand-600">Scheduled: {formatDate(order.scheduled_collection_time)}</span>
                    )}
                  </div>
                </div>

                {/* Actions */}
                {(isStaff || isManager) && (
                  <div className="flex gap-2 flex-shrink-0">
                    {order.status === "pending" && (isManager || isStaff) && (
                      <>
                        <Button
                          size="sm"
                          variant="primary"
                          loading={actionLoading === order.id}
                          onClick={() => handleAction(order.id, () => confirmOrder(order.id))}
                        >
                          Confirm
                        </Button>
                        {isManager && (
                          <Button
                            size="sm"
                            variant="danger"
                            loading={actionLoading === order.id}
                            onClick={() => {
                              const reason = prompt("Rejection reason:");
                              if (reason) handleAction(order.id, () => rejectOrder(order.id, reason));
                            }}
                          >
                            Reject
                          </Button>
                        )}
                      </>
                    )}
                    {order.status === "pending" && (
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
                    {order.status === "ready" && isManager && (
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => {
                          const mins = prompt("Additional minutes:");
                          if (mins) handleAction(order.id, () => delayOrder(order.id, parseInt(mins)));
                        }}
                      >
                        Delay
                      </Button>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
