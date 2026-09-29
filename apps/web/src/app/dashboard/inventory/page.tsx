"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import { getCafeterias, getInventory, adjustInventory } from "@/lib/api";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { EmptyState } from "@/components/ui/EmptyState";
import { Button } from "@/components/ui/Button";
import type { Cafeteria, InventoryItem } from "@uniserve/shared-types";

export default function InventoryPage() {
  const { user } = useAuth();
  const router = useRouter();
  const isManager = user?.role === "cafeteria_manager";
  const isStaff = user?.role === "cafeteria_staff";
  const isAdmin = user?.role === "university_admin";
  const canAdjust = isManager || isStaff || isAdmin;
  const hasAccess = isManager || isStaff || isAdmin;

  useEffect(() => {
    if (user && !hasAccess) {
      router.push("/dashboard");
    }
  }, [user, hasAccess, router]);

  const [cafeterias, setCafeterias] = useState<Cafeteria[]>([]);
  const [selectedCafeteria, setSelectedCafeteria] = useState("");
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [lowOnly, setLowOnly] = useState(false);
  const [adjustingItem, setAdjustingItem] = useState<string | null>(null);

  const loadCafeterias = useCallback(async () => {
    try {
      const data = await getCafeterias();
      setCafeterias(data);
      if (data.length > 0 && !selectedCafeteria) setSelectedCafeteria(data[0].id);
    } catch {}
  }, [selectedCafeteria]);

  const loadInventory = useCallback(async () => {
    if (!selectedCafeteria) return;
    setLoading(true);
    try {
      const data = await getInventory(selectedCafeteria, lowOnly);
      setItems(data.items ?? []);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [selectedCafeteria, lowOnly]);

  useEffect(() => { loadCafeterias(); }, [loadCafeterias]);
  useEffect(() => { loadInventory(); }, [loadInventory]);

  const handleAdjust = async (itemId: string) => {
    const qty = prompt("Adjustment quantity (positive = add, negative = subtract):");
    if (!qty) return;
    const reason = prompt("Reason (optional):") ?? undefined;
    setAdjustingItem(itemId);
    try {
      await adjustInventory(selectedCafeteria, {
        inventory_item_id: itemId,
        adjustment_quantity: Number(qty),
        reason,
      });
      await loadInventory();
    } catch (err: any) {
      alert(err?.message ?? "Failed");
    } finally {
      setAdjustingItem(null);
    }
  };

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Inventory"
        description="Track and adjust stock levels"
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
            <button
              onClick={() => setLowOnly(!lowOnly)}
              className={`px-3 py-2 text-sm rounded-lg border transition-colors ${
                lowOnly
                  ? "bg-orange-50 border-orange-300 text-orange-700 dark:bg-orange-900/30 dark:border-orange-700 dark:text-orange-400"
                  : "border-[var(--border-default)] text-[var(--text-secondary)] hover:bg-[var(--bg-secondary)]"
              }`}
            >
              {lowOnly ? "⚠ Low Stock Only" : "All Items"}
            </button>
          </div>
        }
      />

      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-16 bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl skeleton" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          title="No inventory items"
          description="Inventory items for this cafeteria will appear here."
          icon={
            <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
            </svg>
          }
        />
      ) : (
        <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl overflow-hidden shadow-card">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border-default)] bg-[var(--bg-secondary)]/50">
                  <th className="px-4 py-3 text-left text-xs font-semibold text-[var(--text-muted)] uppercase">Item</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-[var(--text-muted)] uppercase">Quantity</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-[var(--text-muted)] uppercase">Unit</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-[var(--text-muted)] uppercase">Low Threshold</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-[var(--text-muted)] uppercase">Status</th>
                  {canAdjust && (
                    <th className="px-4 py-3 text-right text-xs font-semibold text-[var(--text-muted)] uppercase">Action</th>
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-default)]">
                {items.map((item) => (
                  <tr key={item.id} className="hover:bg-[var(--bg-secondary)]/50 transition-colors">
                    <td className="px-4 py-3 font-medium text-[var(--text-primary)]">
                      {(item as any).menu_item?.name ?? item.menu_item_id.slice(0, 8)}
                    </td>
                    <td className="px-4 py-3 text-[var(--text-primary)]">{item.quantity}</td>
                    <td className="px-4 py-3 text-[var(--text-secondary)] capitalize">{item.unit}</td>
                    <td className="px-4 py-3 text-[var(--text-secondary)]">{item.low_threshold}</td>
                    <td className="px-4 py-3">
                      <StatusBadge
                        status={
                          item.quantity <= 0
                            ? "out_of_stock"
                            : item.is_low
                            ? "low"
                            : "active"
                        }
                      />
                    </td>
                    {canAdjust && (
                      <td className="px-4 py-3 text-right">
                        <Button
                          size="sm"
                          variant="ghost"
                          loading={adjustingItem === item.id}
                          onClick={() => handleAdjust(item.id)}
                        >
                          Adjust
                        </Button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
