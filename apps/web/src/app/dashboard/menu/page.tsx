"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import { getCafeterias, getMenuItems, updateMenuItem, createMenuItem, getDailyMenus, createDailyMenu, addDailyMenuItem, publishDailyMenu, removeDailyMenuItem } from "@/lib/api";
import { useToast } from "@/components/ui/Toast";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { EmptyState } from "@/components/ui/EmptyState";
import { Button } from "@/components/ui/Button";
import type { Cafeteria, DailyMenu, MenuItem } from "@uniserve/shared-types";

const CATEGORIES = ["all", "breakfast", "main_course", "side_dish", "dessert", "beverage", "snack", "salad", "soup"] as const;

export default function MenuPage() {
  const { user } = useAuth();
  const router = useRouter();
  const isManager = user?.role === "cafeteria_manager";
  const isStaff = user?.role === "cafeteria_staff";
  const isAdmin = user?.role === "university_admin";
  const canEdit = isManager || isAdmin;
  const hasAccess = isManager || isStaff || isAdmin;

  useEffect(() => {
    if (user && !hasAccess) {
      router.push("/dashboard");
    }
  }, [user, hasAccess, router]);

  const [cafeterias, setCafeterias] = useState<Cafeteria[]>([]);
  const [selectedCafeteria, setSelectedCafeteria] = useState("");
  const [category, setCategory] = useState("all");
  const [items, setItems] = useState<MenuItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [editItem, setEditItem] = useState<MenuItem | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  /* Today's daily-menu workflow (manager/admin — backend write scope) */
  const [dailyMenu, setDailyMenu] = useState<DailyMenu | null>(null);
  const [dailyLoading, setDailyLoading] = useState(false);
  const [showAddDailyItem, setShowAddDailyItem] = useState(false);
  const { toast } = useToast();

  const loadCafeterias = useCallback(async () => {
    try {
      const data = await getCafeterias();
      setCafeterias(data);
      if (data.length > 0 && !selectedCafeteria) setSelectedCafeteria(data[0].id);
    } catch {}
  }, [selectedCafeteria]);

  const loadItems = useCallback(async () => {
    if (!selectedCafeteria) return;
    setLoading(true);
    try {
      const data = await getMenuItems(selectedCafeteria, {
        category: category !== "all" ? category : undefined,
        search: searchQuery || undefined,
      });
      setItems(data.items ?? []);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [selectedCafeteria, category, searchQuery]);

  useEffect(() => { loadCafeterias(); }, [loadCafeterias]);
  useEffect(() => { loadItems(); }, [loadItems]);

  const todayISO = () => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
  };

  const loadDailyMenu = useCallback(async () => {
    if (!selectedCafeteria) return;
    try {
      const data = await getDailyMenus(selectedCafeteria);
      const today = todayISO();
      const menu = (data.menus ?? []).find((m: DailyMenu) => m.menu_date === today) ?? null;
      setDailyMenu(menu);
    } catch {
      setDailyMenu(null);
    }
  }, [selectedCafeteria]);

  useEffect(() => { loadDailyMenu(); }, [loadDailyMenu]);

  const toggleAvailability = async (item: MenuItem) => {
    try {
      await updateMenuItem(selectedCafeteria, item.id, { is_available: !item.is_available });
      await loadItems();
      toast("Availability updated", "success");
    } catch (err: any) {
      toast(err?.message ?? "Failed", "error");
    }
  };

  const toggleActive = async (item: MenuItem) => {
    try {
      await updateMenuItem(selectedCafeteria, item.id, { is_active: !item.is_active });
      await loadItems();
      toast("Status updated", "success");
    } catch (err: any) {
      toast(err?.message ?? "Failed", "error");
    }
  };

  const handleCreateDailyMenu = async () => {
    setDailyLoading(true);
    try {
      const menu = await createDailyMenu(selectedCafeteria, todayISO());
      setDailyMenu(menu);
      toast("Daily menu draft created", "success");
    } catch (err: any) {
      toast(err?.message ?? "Failed to create daily menu", "error");
    } finally {
      setDailyLoading(false);
    }
  };

  const handlePublishDailyMenu = async () => {
    if (!dailyMenu) return;
    setDailyLoading(true);
    try {
      const menu = await publishDailyMenu(selectedCafeteria, dailyMenu.id);
      setDailyMenu(menu);
      toast("Daily menu published", "success");
    } catch (err: any) {
      // e.g. "Cannot publish an empty menu" — reload to resync state
      toast(err?.message ?? "Failed to publish daily menu", "error");
      await loadDailyMenu();
    } finally {
      setDailyLoading(false);
    }
  };

  const handleRemoveDailyItem = async (menuItemId: string) => {
    if (!dailyMenu) return;
    setDailyLoading(true);
    try {
      const menu = await removeDailyMenuItem(selectedCafeteria, dailyMenu.id, menuItemId);
      setDailyMenu(menu);
      toast("Item removed from daily menu", "success");
    } catch (err: any) {
      toast(err?.message ?? "Failed to remove item", "error");
    } finally {
      setDailyLoading(false);
    }
  };

  const formatPrice = (p: number) => `PKR ${Math.round(p / 100)}`;

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Menu Management"
        description="Manage menu items and daily availability"
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
            {canEdit && (
              <Button size="sm" onClick={() => setShowCreate(true)}>Add Item</Button>
            )}
          </div>
        }
      />

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-6">
        <input
          type="text"
          placeholder="Search menu items..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="px-3 py-2 text-sm border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)] w-64"
        />
        <div className="flex gap-1 overflow-x-auto">
          {CATEGORIES.map((cat) => (
            <button
              key={cat}
              onClick={() => setCategory(cat)}
              className={`px-3 py-1.5 text-xs font-medium rounded-full capitalize transition-colors whitespace-nowrap ${
                category === cat
                  ? "bg-brand-600 text-white"
                  : "bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:bg-brand-50 dark:hover:bg-brand-900/30"
              }`}
            >
              {cat.replace(/_/g, " ")}
            </button>
          ))}
        </div>
      </div>

      {/* ─── Today's daily menu (manager/admin; backend enforces write scope) ─── */}
      {canEdit && (
        <div className="mb-6 bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl p-4 shadow-card">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h2 className="text-sm font-semibold text-[var(--text-primary)]">Today&apos;s Daily Menu</h2>
              <p className="text-xs text-[var(--text-muted)]">
                {dailyMenu ? `Date: ${dailyMenu.menu_date}` : "No menu for today yet"}
              </p>
            </div>
            <div className="flex items-center gap-2">
              {dailyMenu && <StatusBadge status={dailyMenu.status} />}
              {dailyMenu?.status === "draft" && (
                <>
                  <Button size="sm" variant="secondary" disabled={dailyLoading} onClick={() => setShowAddDailyItem(true)}>
                    Add Item
                  </Button>
                  <Button size="sm" loading={dailyLoading} onClick={handlePublishDailyMenu}>
                    Publish
                  </Button>
                </>
              )}
              {!dailyMenu && (
                <Button size="sm" loading={dailyLoading} onClick={handleCreateDailyMenu}>
                  Create Draft for Today
                </Button>
              )}
            </div>
          </div>

          {dailyMenu &&
            (dailyMenu.items.length === 0 ? (
              <p className="text-xs text-[var(--text-muted)]">
                No items yet — add menu items from today&apos;s catalog before publishing.
              </p>
            ) : (
              <div className="mb-2">
                {dailyMenu.items.map((entry) => (
                  <div
                    key={entry.id}
                    className="flex items-center gap-2 text-sm py-1.5 border-b border-[var(--border-default)] last:border-0"
                  >
                    <span className="text-xs text-[var(--text-muted)] w-6">#{entry.display_order}</span>
                    <span className="text-[var(--text-primary)] flex-1 truncate">
                      {entry.menu_item?.name ?? "Menu item"}
                    </span>
                    <span className="text-xs text-[var(--text-secondary)]">
                      {formatPrice(entry.special_price ?? entry.menu_item?.price ?? 0)}
                    </span>
                    <StatusBadge status={entry.is_available_today ? "active" : "closed"} />
                    {dailyMenu.status === "draft" && (
                      <button
                        onClick={() => handleRemoveDailyItem(entry.menu_item_id)}
                        className="text-xs text-red-600 hover:text-red-500 font-medium"
                      >
                        Remove
                      </button>
                    )}
                  </div>
                ))}
              </div>
            ))}

          {dailyMenu?.status === "published" && (
            <p className="text-xs text-green-700 dark:text-green-400">
              Published — students see this menu today.
            </p>
          )}
        </div>
      )}

      {/* Menu items grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="h-40 bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl skeleton" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          title="No menu items"
          description="No items found for this filter."
          icon={
            <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
          }
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((item) => (
            <div
              key={item.id}
              className={`bg-[var(--bg-primary)] border rounded-xl p-4 shadow-card transition-all ${
                !item.is_active
                  ? "opacity-50 border-neutral-200 dark:border-neutral-700"
                  : "border-[var(--border-default)] hover:shadow-card-hover"
              }`}
            >
              <div className="flex items-start justify-between mb-2">
                <div className="min-w-0 flex-1">
                  <h3 className="text-sm font-semibold text-[var(--text-primary)] truncate">{item.name}</h3>
                  <p className="text-xs text-[var(--text-muted)] capitalize mt-0.5">{item.category.replace(/_/g, " ")}</p>
                </div>
                <span className="text-sm font-bold text-brand-700 dark:text-brand-400">{formatPrice(item.price)}</span>
              </div>

              {item.description && (
                <p className="text-xs text-[var(--text-secondary)] mb-3 line-clamp-2">{item.description}</p>
              )}

              <div className="flex items-center gap-2 mb-3">
                <StatusBadge status={item.is_available ? "active" : "closed"} />
                <span className="text-xs text-[var(--text-muted)]">{item.preparation_time_minutes}min</span>
              </div>

              {canEdit && (
                <div className="flex gap-2 pt-2 border-t border-[var(--border-default)]">
                  <button
                    onClick={() => toggleAvailability(item)}
                    className="text-xs text-brand-700 dark:text-brand-400 hover:text-brand-600 font-medium"
                  >
                    {item.is_available ? "Mark Unavailable" : "Mark Available"}
                  </button>
                  <button
                    onClick={() => toggleActive(item)}
                    className="text-xs text-red-600 hover:text-red-500 font-medium"
                  >
                    {item.is_active ? "Deactivate" : "Activate"}
                  </button>
                  <button
                    onClick={() => setEditItem(item)}
                    className="text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] font-medium ml-auto"
                  >
                    Edit
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Edit/Create modal */}
      {(editItem || showCreate) && (
        <MenuItemModal
          cafeteriaId={selectedCafeteria}
          item={editItem}
          onClose={() => { setEditItem(null); setShowCreate(false); }}
          onSaved={() => { setEditItem(null); setShowCreate(false); loadItems(); }}
        />
      )}

      {/* Add item to daily menu modal */}
      {showAddDailyItem && dailyMenu && (
        <DailyMenuItemModal
          cafeteriaId={selectedCafeteria}
          dailyMenuId={dailyMenu.id}
          menuItems={items}
          existingItemIds={dailyMenu.items.map((i) => i.menu_item_id)}
          onClose={() => setShowAddDailyItem(false)}
          onSaved={(menu) => { setDailyMenu(menu); setShowAddDailyItem(false); }}
        />
      )}
    </div>
  );
}

function MenuItemModal({
  cafeteriaId,
  item,
  onClose,
  onSaved,
}: {
  cafeteriaId: string;
  item: MenuItem | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [form, setForm] = useState({
    name: item?.name ?? "",
    description: item?.description ?? "",
    category: item?.category ?? "main_course",
    price: item ? Math.round(item.price / 100) : 0,
    preparation_time_minutes: item?.preparation_time_minutes ?? 15,
  });
  const [saving, setSaving] = useState(false);
  const { toast } = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      if (item) {
        await updateMenuItem(cafeteriaId, item.id, {
          ...form,
          price: form.price * 100,
        });
      } else {
        await createMenuItem(cafeteriaId, {
          ...form,
          price: form.price * 100,
          currency: "PKR",
        });
      }
      onSaved();
    } catch (err: any) {
      toast(err?.message ?? "Failed to save menu item", "error");
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
        <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-4">
          {item ? "Edit Menu Item" : "Add Menu Item"}
        </h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1">Name</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="w-full px-3 py-2 text-sm border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)]"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1">Description</label>
            <textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              className="w-full px-3 py-2 text-sm border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)]"
              rows={2}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1">Category</label>
              <select
                value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value as any })}
                className="w-full px-3 py-2 text-sm border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)]"
              >
                {["breakfast", "main_course", "side_dish", "dessert", "beverage", "snack", "salad", "soup"].map((c) => (
                  <option key={c} value={c}>{c.replace(/_/g, " ")}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1">Price (PKR)</label>
              <input
                type="number"
                value={form.price}
                onChange={(e) => setForm({ ...form, price: Number(e.target.value) })}
                className="w-full px-3 py-2 text-sm border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)]"
                min={0}
                required
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1">Prep Time (min)</label>
            <input
              type="number"
              value={form.preparation_time_minutes}
              onChange={(e) => setForm({ ...form, preparation_time_minutes: Number(e.target.value) })}
              className="w-full px-3 py-2 text-sm border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)]"
              min={1}
            />
          </div>
          <div className="flex gap-2 justify-end pt-2">
            <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
            <Button type="submit" loading={saving}>{item ? "Save Changes" : "Create"}</Button>
          </div>
        </form>
      </div>
    </div>
  );
}

function DailyMenuItemModal({
  cafeteriaId,
  dailyMenuId,
  menuItems,
  existingItemIds,
  onClose,
  onSaved,
}: {
  cafeteriaId: string;
  dailyMenuId: string;
  menuItems: MenuItem[];
  existingItemIds: string[];
  onClose: () => void;
  onSaved: (menu: DailyMenu) => void;
}) {
  // Addable = active catalog items not already on today's daily menu
  const addable = menuItems.filter(
    (m) => m.is_active !== false && !existingItemIds.includes(m.id),
  );
  const [form, setForm] = useState({
    menu_item_id: addable[0]?.id ?? "",
    specialPrice: 0,
    displayOrder: 0,
    isAvailableToday: true,
  });
  const [saving, setSaving] = useState(false);
  const { toast } = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.menu_item_id) return;
    setSaving(true);
    try {
      // Matches DailyMenuAddItemRequest: special_price in paisa (>0),
      // display_order >= 0, is_available_today bool
      const menu = await addDailyMenuItem(cafeteriaId, dailyMenuId, {
        menu_item_id: form.menu_item_id,
        ...(form.specialPrice > 0 ? { special_price: form.specialPrice * 100 } : {}),
        display_order: form.displayOrder,
        is_available_today: form.isAvailableToday,
      });
      onSaved(menu);
    } catch (err: any) {
      toast(err?.message ?? "Failed to add item to daily menu", "error");
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
        <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-4">Add Item to Daily Menu</h2>
        {addable.length === 0 ? (
          <p className="text-sm text-[var(--text-secondary)] mb-4">
            No menu items available to add — create or activate items in the catalog first.
          </p>
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
                {addable.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name} — PKR {Math.round(m.price / 100)}
                  </option>
                ))}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1">
                  Special Price (PKR, optional)
                </label>
                <input
                  type="number"
                  min={0}
                  value={form.specialPrice}
                  onChange={(e) => setForm({ ...form, specialPrice: Number(e.target.value) })}
                  className="w-full px-3 py-2 text-sm border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)]"
                  placeholder="Regular price"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1">Display Order</label>
                <input
                  type="number"
                  min={0}
                  value={form.displayOrder}
                  onChange={(e) => setForm({ ...form, displayOrder: Number(e.target.value) })}
                  className="w-full px-3 py-2 text-sm border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)]"
                />
              </div>
            </div>
            <label className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
              <input
                type="checkbox"
                checked={form.isAvailableToday}
                onChange={(e) => setForm({ ...form, isAvailableToday: e.target.checked })}
              />
              Available today
            </label>
            <div className="flex gap-2 justify-end pt-2">
              <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
              <Button type="submit" loading={saving} disabled={addable.length === 0}>Add to Daily Menu</Button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
