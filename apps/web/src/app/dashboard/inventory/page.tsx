"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import { getCafeterias, getMyCafeterias, getInventory, getMenuItems, adjustInventory, createInventoryItem, ApiClientError, getApiErrorInfo } from "@/lib/api";
import type { ApiErrorInfo } from "@/lib/api";
import { useToast } from "@/components/ui/Toast";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadErrorState } from "@/components/ui/LoadErrorState";
import { Button } from "@/components/ui/Button";
import type { Cafeteria, InventoryItem, MenuItem } from "@uniserve/shared-types";

export default function InventoryPage() {
  const { user } = useAuth();
  const router = useRouter();
  const isManager = user?.role === "cafeteria_manager";
  const isStaff = user?.role === "cafeteria_staff";
  const isAdmin = user?.role === "university_admin";
  const canAdjust = isManager || isStaff || isAdmin;
  /* Phase 56 — inventory CREATE is manager/admin only (backend write scope
     excludes staff, who keep adjust rights). */
  const canCreate = isManager || isAdmin;
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
  /* P3-4 — menu_item_id → display name map so the table shows real item
     names instead of raw UUID prefixes. */
  const [menuNames, setMenuNames] = useState<Record<string, string>>({});
  /* P3-2 — explicit permission state when a scoped inventory load 403s */
  const [accessError, setAccessError] = useState<string | null>(null);
  /* Phase 46 — request-failure states (distinct from the 403 accessError) */
  const [loadError, setLoadError] = useState<ApiErrorInfo | null>(null);
  const [cafeteriasError, setCafeteriasError] = useState<ApiErrorInfo | null>(null);
  const { toast } = useToast();

  /* Inline modal state — replaces window.prompt */
  const [adjustModal, setAdjustModal] = useState<{ itemId: string; quantity: string; reason: string } | null>(null);
  /* Phase 56 — add inventory item modal (manager/admin) */
  const [showCreate, setShowCreate] = useState(false);

  const loadCafeterias = useCallback(async () => {
    try {
      // Phase 56 — inventory management is an operational surface: only
      // ACTIVE cafeterias are offered. Inactive cafeterias remain visible
      // to admins on the Cafeterias admin page.
      const data = await getCafeterias({ isActive: true });
      // P3-3 — staff/manager selectors default to (and only offer) the
      // cafeterias the user is actually assigned to. Admin keeps all.
      let visible = data;
      if (isStaff || isManager) {
        const assigned = await getMyCafeterias();
        if (assigned.length > 0) {
          visible = data.filter((c) => assigned.includes(c.id));
        }
      }
      setCafeterias(visible);
      setCafeteriasError(null);
      if (visible.length > 0 && !selectedCafeteria) {
        setSelectedCafeteria(visible[0].id);
      }
    } catch (err) {
      // Phase 46 — surface the selector load failure; never render a
      // silently empty cafeteria selector.
      setCafeteriasError(getApiErrorInfo(err));
    }
  }, [selectedCafeteria, isStaff, isManager]);

  const loadInventory = useCallback(async () => {
    if (!selectedCafeteria) return;
    setLoading(true);
    setAccessError(null);
    try {
      const data = await getInventory(selectedCafeteria, lowOnly);
      setItems(data.items ?? []);
      setLoadError(null);
      // P3-4 — resolve display names for the inventory rows. Best-effort:
      // if the catalog fetch fails, rows fall back to the id prefix.
      try {
        const menu = await getMenuItems(selectedCafeteria);
        const names: Record<string, string> = {};
        for (const mi of menu.items ?? []) {
          names[mi.id] = mi.name;
        }
        setMenuNames(names);
      } catch {
        setMenuNames({});
      }
    } catch (err: any) {
      // P3-2 — scoped 403 renders an explicit access notice, not an
      // "empty inventory" state. Phase 46 — any other failure (5xx,
      // network, timeout) becomes a retryable error state; previously
      // loaded items stay on screen.
      if (err instanceof ApiClientError && err.status === 403) {
        setAccessError(
          err.message || "You do not have access to this cafeteria's inventory.",
        );
        setItems([]);
        setLoadError(null);
      } else {
        setLoadError(getApiErrorInfo(err));
      }
    } finally {
      setLoading(false);
    }
  }, [selectedCafeteria, lowOnly]);

  useEffect(() => { loadCafeterias(); }, [loadCafeterias]);
  useEffect(() => { loadInventory(); }, [loadInventory]);

  const handleAdjust = async (itemId: string, quantity: number, reason?: string) => {
    setAdjustingItem(itemId);
    try {
      await adjustInventory(selectedCafeteria, {
        inventory_item_id: itemId,
        adjustment_quantity: quantity,
        reason,
      });
      await loadInventory();
      toast("Inventory adjusted", "success");
    } catch (err: any) {
      toast(err?.message ?? "Failed", "error");
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
            {/* Phase 56 — create an inventory record for a menu item */}
            {canCreate && (
              <Button size="sm" onClick={() => setShowCreate(true)}>Add Item</Button>
            )}
          </div>
        }
      />

      {/* Phase 46 — cafeteria selector load failure (compact, retryable) */}
      {cafeteriasError && (
        <LoadErrorState
          compact
          error={cafeteriasError}
          subject="cafeterias"
          onRetry={() => loadCafeterias()}
          className="mb-4 border border-red-200 dark:border-red-800 bg-red-50/50 dark:bg-red-900/10 rounded-xl"
        />
      )}
      {/* Phase 46 — inventory refresh failure (compact, retryable) */}
      {loadError && items.length > 0 && (
        <LoadErrorState
          compact
          error={loadError}
          subject="inventory items"
          onRetry={() => loadInventory()}
          className="mb-4 border border-red-200 dark:border-red-800 bg-red-50/50 dark:bg-red-900/10 rounded-xl"
        />
      )}

      {/* P3-2 — explicit permission notice when the scoped load 403s */}
      {accessError && !loading && (
        <div className="mb-6 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl p-4">
          <p className="text-sm font-medium text-amber-800 dark:text-amber-300">
            Access restricted
          </p>
          <p className="text-xs text-amber-700 dark:text-amber-400 mt-1">
            {accessError}
          </p>
        </div>
      )}

      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-16 bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl skeleton" />
          ))}
        </div>
      ) : loadError && items.length === 0 ? (
        <LoadErrorState
          error={loadError}
          subject="inventory items"
          onRetry={() => loadInventory()}
        />
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
                      {/* P3-4 — resolved menu item name; id prefix only as a
                          last-resort fallback when the catalog is unavailable */}
                      {menuNames[item.menu_item_id] ??
                        (item as any).menu_item?.name ??
                        `Item ${item.menu_item_id.slice(0, 8)}…`}
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
                          onClick={() => setAdjustModal({ itemId: item.id, quantity: "", reason: "" })}
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

      {/* ─── Adjust inventory modal ─── */}
      {adjustModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setAdjustModal(null)}>
          <div
            className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl shadow-xl w-full max-w-sm mx-4 p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-base font-semibold text-[var(--text-primary)] mb-3">Adjust Inventory</h3>
            <label className="block text-sm text-[var(--text-secondary)] mb-1">Quantity (positive = add, negative = subtract)</label>
            <input
              type="number"
              value={adjustModal.quantity}
              onChange={(e) => setAdjustModal({ ...adjustModal, quantity: e.target.value })}
              className="w-full px-3 py-2 text-sm border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)]"
              placeholder="e.g. 10 or -5"
              autoFocus
            />
            <label className="block text-sm text-[var(--text-secondary)] mt-3 mb-1">Reason (optional)</label>
            <input
              type="text"
              value={adjustModal.reason}
              onChange={(e) => setAdjustModal({ ...adjustModal, reason: e.target.value })}
              className="w-full px-3 py-2 text-sm border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)]"
              placeholder="e.g. Restocked from supplier"
            />
            <div className="flex justify-end gap-2 mt-4">
              <Button size="sm" variant="ghost" onClick={() => setAdjustModal(null)}>Cancel</Button>
              <Button
                size="sm"
                variant="primary"
                loading={adjustingItem === adjustModal.itemId}
                onClick={() => {
                  const qty = parseInt(adjustModal.quantity);
                  if (isNaN(qty)) return;
                  handleAdjust(adjustModal.itemId, qty, adjustModal.reason || undefined);
                  setAdjustModal(null);
                }}
              >
                Confirm
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Phase 56 — add inventory item (manager/admin write scope) */}
      {showCreate && (
        <CreateInventoryItemModal
          cafeteriaId={selectedCafeteria}
          existingMenuIds={items.map((i) => i.menu_item_id)}
          onClose={() => setShowCreate(false)}
          onSaved={() => {
            setShowCreate(false);
            loadInventory();
            toast("Inventory item created", "success");
          }}
        />
      )}
    </div>
  );
}

/* Phase 56 — create an inventory record for a menu item. Candidates:
   ACTIVE catalog items without an existing inventory record for this
   cafeteria (backend enforces one record per item via upsert + the
   wrong-cafeteria 403). Quantity/threshold are >= 0; unit uses the
   backend's lowercase InventoryUnit values. */
function CreateInventoryItemModal({
  cafeteriaId,
  existingMenuIds,
  onClose,
  onSaved,
}: {
  cafeteriaId: string;
  existingMenuIds: string[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [candidates, setCandidates] = useState<MenuItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadErr, setLoadErr] = useState<ApiErrorInfo | null>(null);
  const [submitErr, setSubmitErr] = useState<ApiErrorInfo | null>(null);
  const [form, setForm] = useState({
    menu_item_id: "",
    quantity: "",
    unit: "portions",
    low_threshold: "",
  });
  const [saving, setSaving] = useState(false);

  const loadCatalog = useCallback(async () => {
    setLoading(true);
    setLoadErr(null);
    try {
      const data = await getMenuItems(cafeteriaId);
      const addable = (data.items ?? []).filter(
        (mi: MenuItem) => mi.is_active !== false && !existingMenuIds.includes(mi.id),
      );
      setCandidates(addable);
      setForm((f) => ({ ...f, menu_item_id: f.menu_item_id || addable[0]?.id || "" }));
    } catch (err) {
      setLoadErr(getApiErrorInfo(err));
    } finally {
      setLoading(false);
    }
  }, [cafeteriaId, existingMenuIds]);

  useEffect(() => { loadCatalog(); }, [loadCatalog]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitErr(null);
    const quantity = Number(form.quantity);
    const lowThreshold = Number(form.low_threshold);
    if (!form.menu_item_id) return;
    if (!Number.isInteger(quantity) || quantity < 0 || !Number.isInteger(lowThreshold) || lowThreshold < 0) {
      setSubmitErr({
        kind: "client",
        message: "Quantity and low threshold must be whole numbers of 0 or more.",
        status: 400,
        retryable: false,
      });
      return;
    }
    setSaving(true);
    try {
      await createInventoryItem(cafeteriaId, {
        menu_item_id: form.menu_item_id,
        quantity,
        unit: form.unit,
        low_threshold: lowThreshold,
      });
      onSaved();
    } catch (err) {
      setSubmitErr(getApiErrorInfo(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl shadow-xl w-full max-w-md mx-4 p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-base font-semibold text-[var(--text-primary)] mb-3">Add Inventory Item</h3>
        {loadErr ? (
          <LoadErrorState error={loadErr} subject="menu catalog" onRetry={() => loadCatalog()} />
        ) : loading ? (
          <p className="text-sm text-[var(--text-muted)]">Loading menu catalog…</p>
        ) : candidates.length === 0 ? (
          <EmptyState
            title="No items to add"
            description="Every active menu item already has an inventory record for this cafeteria."
          />
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1">Menu Item</label>
              <select
                value={form.menu_item_id}
                onChange={(e) => setForm({ ...form, menu_item_id: e.target.value })}
                className="w-full px-3 py-2 text-sm border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)]"
                required
              >
                {candidates.map((mi) => (
                  <option key={mi.id} value={mi.id}>
                    {mi.name} — PKR {Math.round(mi.price / 100)}
                  </option>
                ))}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1">Quantity</label>
                <input
                  type="number"
                  min={0}
                  step={1}
                  value={form.quantity}
                  onChange={(e) => setForm({ ...form, quantity: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)]"
                  required
                  autoFocus
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1">Unit</label>
                <select
                  value={form.unit}
                  onChange={(e) => setForm({ ...form, unit: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)]"
                >
                  {["portions", "kg", "g", "L", "mL", "pcs"].map((u) => (
                    <option key={u} value={u}>{u}</option>
                  ))}
                </select>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1">Low-stock Threshold</label>
              <input
                type="number"
                min={0}
                step={1}
                value={form.low_threshold}
                onChange={(e) => setForm({ ...form, low_threshold: e.target.value })}
                className="w-full px-3 py-2 text-sm border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)]"
                required
              />
            </div>
            {submitErr && (
              <div className="bg-red-50 dark:bg-red-900/10 border border-red-200 dark:border-red-800 rounded-lg p-3">
                <p className="text-sm font-medium text-red-800 dark:text-red-300">{submitErr.message}</p>
              </div>
            )}
            <div className="flex gap-2 justify-end pt-2">
              <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
              <Button type="submit" loading={saving} disabled={!form.menu_item_id}>Create</Button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
