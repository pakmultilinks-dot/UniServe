"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import { getCafeterias, getMyCafeterias, getMenuItems, updateMenuItem, createMenuItem, deleteMenuItem, getDailyMenus, createDailyMenu, copyDailyMenu, addDailyMenuItem, publishDailyMenu, unpublishDailyMenu, removeDailyMenuItem, uploadMenuItemImage, removeMenuItemImage, ApiClientError, getApiErrorInfo } from "@/lib/api";
import type { ApiErrorInfo } from "@/lib/api";
import { resolveApiImageUrl } from "@/lib/imageUrl";
import { formatPricePKR } from "@/lib/format";
import { useToast } from "@/components/ui/Toast";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadErrorState } from "@/components/ui/LoadErrorState";
import { Button } from "@/components/ui/Button";
import type { Cafeteria, DailyMenu, MenuItem } from "@uniserve/shared-types";

const CATEGORIES = ["all", "breakfast", "main_course", "side_dish", "dessert", "beverage", "snack", "salad", "soup"] as const;

/* Phase 56 — canonical dietary/allergen tags. Persisted as JSON array
   strings on the existing Text columns (no migration needed); rendered as
   chips on cards and edited via toggle chips in the item modal. */
const DIETARY_TAGS = ["vegetarian", "vegan", "halal", "gluten_free"] as const;
const ALLERGEN_TAGS = ["milk", "eggs", "wheat", "peanuts", "tree_nuts", "soy"] as const;

/** Parse a dietary_info/allergens value (JSON array string, plain string,
    or already-parsed array) into a string[] for chip rendering/editing. */
const parseTags = (raw: unknown): string[] => {
  if (Array.isArray(raw)) return raw.filter((v): v is string => typeof v === "string");
  if (typeof raw === "string" && raw.trim()) {
    try {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) return parsed.filter((v): v is string => typeof v === "string");
    } catch {
      return raw.split(",").map((t) => t.trim()).filter(Boolean);
    }
  }
  return [];
};

const humanizeTag = (t: string) => t.replace(/_/g, " ");

/** ISO yyyy-mm-dd (local time) — used by the Phase 56 copy modal. */
const isoDate = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

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
  const [debouncedSearchQuery, setDebouncedSearchQuery] = useState("");
  const [editItem, setEditItem] = useState<MenuItem | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  /* Today's daily-menu workflow (manager/admin — backend write scope) */
  const [dailyMenu, setDailyMenu] = useState<DailyMenu | null>(null);
  const [dailyLoading, setDailyLoading] = useState(false);
  const [showAddDailyItem, setShowAddDailyItem] = useState(false);
  /* P3-2 — explicit permission state for scoped loads that 403 */
  const [itemsError, setItemsError] = useState<string | null>(null);
  /* Phase 46 — request-failure states (distinct from the 403 itemsError).
     A failed load must never masquerade as an empty menu, an empty
     cafeteria selector, or "no menu for today". */
  const [loadError, setLoadError] = useState<ApiErrorInfo | null>(null);
  const [cafeteriasError, setCafeteriasError] = useState<ApiErrorInfo | null>(null);
  const [dailyMenuError, setDailyMenuError] = useState<ApiErrorInfo | null>(null);
  /* WS4 — confirm before unpublishing today's published menu */
  const [confirmUnpublish, setConfirmUnpublish] = useState(false);
  /* 48B — image upload modal + image removal confirmation */
  const [imageItem, setImageItem] = useState<MenuItem | null>(null);
  const [confirmRemoveImage, setConfirmRemoveImage] = useState<MenuItem | null>(null);
  const [removeImageLoading, setRemoveImageLoading] = useState(false);
  /* Phase 56 — copy previous day's menu + admin soft-delete states */
  const [showCopyDaily, setShowCopyDaily] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<MenuItem | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const { toast } = useToast();

  const loadCafeterias = useCallback(async () => {
    try {
      // Phase 56 — menu management is an operational surface: only ACTIVE
      // cafeterias are offered here. Inactive cafeterias remain visible to
      // admins on the Cafeterias admin page (and via ?is_active=false).
      const data = await getCafeterias({ isActive: true });
      // P3-3 — staff/manager selectors default to (and only offer) the
      // cafeterias the user is actually assigned to. Admin keeps the full
      // list. If assignment info is unavailable, fall back to all cafeterias
      // (previous behaviour) — the scoped endpoints still enforce access.
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

  // Debounce the search input: without this, every keystroke fires a
  // menu-items API request (loadItems depends on the query string).
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearchQuery(searchQuery), 350);
    return () => clearTimeout(t);
  }, [searchQuery]);

  const loadItems = useCallback(async () => {
    if (!selectedCafeteria) return;
    setLoading(true);
    setItemsError(null);
    try {
      const data = await getMenuItems(selectedCafeteria, {
        category: category !== "all" ? category : undefined,
        search: debouncedSearchQuery || undefined,
      });
      setItems(data.items ?? []);
      setLoadError(null);
    } catch (err: any) {
      // P3-2 — a scoped 403 (e.g. foreign cafeteria) must surface as an
      // explicit permission notice, not masquerade as an empty menu.
      // Phase 46 — any other failure (5xx, network, timeout) becomes a
      // retryable error state; previously loaded items stay on screen.
      if (err instanceof ApiClientError && err.status === 403) {
        setItemsError(
          err.message || "You do not have access to this cafeteria's menu.",
        );
        setItems([]);
        setLoadError(null);
      } else {
        setLoadError(getApiErrorInfo(err));
      }
    } finally {
      setLoading(false);
    }
  }, [selectedCafeteria, category, debouncedSearchQuery]);

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
      // WS4 — today's LIVE menu only. Archived menus (e.g. one unpublished
      // earlier today) must not shadow the active published/draft menu.
      const active = (data.menus ?? []).filter(
        (m: DailyMenu) => m.menu_date === today && m.status !== "archived",
      );
      const menu =
        active.find((m: DailyMenu) => m.status === "published") ??
        active.find((m: DailyMenu) => m.status === "draft") ??
        null;
      setDailyMenu(menu);
      setDailyMenuError(null);
    } catch (err) {
      // Phase 46 — a failed daily-menu request must not masquerade as
      // "No menu for today yet" (that claim is only true after a successful
      // response with no active menu).
      setDailyMenu(null);
      setDailyMenuError(getApiErrorInfo(err));
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

  /** WS4 — unpublish today's published menu (archives it). Students stop
   * seeing it immediately; a replacement draft can then be created. */
  const handleUnpublishDailyMenu = async () => {
    if (!dailyMenu) return;
    setDailyLoading(true);
    try {
      await unpublishDailyMenu(selectedCafeteria, dailyMenu.id);
      setDailyMenu(null);
      toast("Daily menu unpublished — students no longer see it today", "success");
      await loadDailyMenu();
    } catch (err: any) {
      toast(err?.message ?? "Failed to unpublish daily menu", "error");
      await loadDailyMenu();
    } finally {
      setDailyLoading(false);
      setConfirmUnpublish(false);
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

  /** Phase 56 — soft-delete a menu item (admin-only; backend-enforced).
      The item leaves the active catalog and future menus; historical daily
      menus, order snapshots and reports are unaffected by design. */
  const handleDeleteMenuItem = async () => {
    if (!confirmDelete) return;
    setDeleteLoading(true);
    try {
      const name = confirmDelete.name;
      await deleteMenuItem(selectedCafeteria, confirmDelete.id);
      setConfirmDelete(null);
      await loadItems();
      await loadDailyMenu();
      toast(`${name} deleted — historical orders and reports are unaffected`, "success");
    } catch (err) {
      toast(getApiErrorInfo(err).message, "error");
    } finally {
      setDeleteLoading(false);
    }
  };

  const formatPrice = (p: number) => formatPricePKR(p);

  /* 48B — remove image: named confirmation, then the real DELETE endpoint.
     The menu item itself stays fully usable (backend clears image_url only). */
  const handleConfirmRemoveImage = async () => {
    if (!confirmRemoveImage) return;
    setRemoveImageLoading(true);
    try {
      await removeMenuItemImage(selectedCafeteria, confirmRemoveImage.id);
      const name = confirmRemoveImage.name;
      setConfirmRemoveImage(null);
      await loadItems();
      toast(`Image removed from ${name}`, "success");
    } catch (err) {
      toast(getApiErrorInfo(err).message, "error");
    } finally {
      setRemoveImageLoading(false);
    }
  };

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

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-6">
        <input
          type="text"
          aria-label="Search menu items"
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

      {/* ─── Today's daily menu (read-only for staff; management for
           manager/admin — backend enforces the same write scope) ─── */}
      {hasAccess && (
        <div className="mb-6 bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl p-4 shadow-card">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h2 className="text-sm font-semibold text-[var(--text-primary)]">Today&apos;s Daily Menu</h2>
              <p className="text-xs text-[var(--text-muted)]">
                {dailyMenuError
                  ? "Unable to load today's menu status"
                  : dailyMenu
                  ? `Date: ${dailyMenu.menu_date}`
                  : "No menu for today yet"}
              </p>
            </div>
            <div className="flex items-center gap-2">
              {canEdit && (
                <Button size="sm" variant="secondary" onClick={() => setShowCopyDaily(true)}>
                  Copy Previous Day
                </Button>
              )}
              {dailyMenu && <StatusBadge status={dailyMenu.status} />}
              {canEdit && dailyMenu?.status === "draft" && (
                <>
                  <Button size="sm" variant="secondary" disabled={dailyLoading} onClick={() => setShowAddDailyItem(true)}>
                    Add Item
                  </Button>
                  <Button size="sm" loading={dailyLoading} onClick={handlePublishDailyMenu}>
                    Publish
                  </Button>
                </>
              )}
              {canEdit && dailyMenu?.status === "published" && (
                <Button size="sm" variant="danger" disabled={dailyLoading} onClick={() => setConfirmUnpublish(true)}>
                  Unpublish
                </Button>
              )}
              {canEdit && !dailyMenu && !dailyMenuError && (
                <Button size="sm" loading={dailyLoading} onClick={handleCreateDailyMenu}>
                  Create Draft for Today
                </Button>
              )}
              {isStaff && !dailyMenu && (
                <span className="text-xs text-[var(--text-muted)]">Not published yet</span>
              )}
            </div>
          </div>

          {dailyMenuError ? (
            <LoadErrorState
              compact
              error={dailyMenuError}
              subject="today's daily menu"
              onRetry={() => loadDailyMenu()}
            />
          ) : dailyMenu &&
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
                    {canEdit && dailyMenu.status === "draft" && (
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

      {/* P3-2 — explicit permission notice when the scoped load 403s */}
      {itemsError && !loading && (
        <div className="mb-6 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl p-4">
          <p className="text-sm font-medium text-amber-800 dark:text-amber-300">
            Access restricted
          </p>
          <p className="text-xs text-amber-700 dark:text-amber-400 mt-1">
            {itemsError}
          </p>
        </div>
      )}

      {/* Phase 46 — menu catalog refresh failure (compact, retryable) */}
      {loadError && items.length > 0 && (
        <LoadErrorState
          compact
          error={loadError}
          subject="menu items"
          onRetry={() => loadItems()}
          className="mb-6 border border-red-200 dark:border-red-800 bg-red-50/50 dark:bg-red-900/10 rounded-xl"
        />
      )}

      {/* Menu items grid — Phase 46: request failures render an explicit
          retryable error state, never a misleading "No menu items". */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="h-40 bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl skeleton" />
          ))}
        </div>
      ) : itemsError ? null : loadError && items.length === 0 ? (
        <LoadErrorState
          error={loadError}
          subject="menu items"
          onRetry={() => loadItems()}
        />
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
              {/* 48B — thumbnail: host-independent reference resolved at render;
                  no image → existing placeholder styling (icon block). */}
              {resolveApiImageUrl(item.image_url) ? (
                <img
                  src={resolveApiImageUrl(item.image_url) as string}
                  alt={item.name}
                  className="w-full h-32 object-cover rounded-lg mb-3 bg-[var(--bg-secondary)]"
                />
              ) : (
                <div className="w-full h-32 rounded-lg mb-3 bg-[var(--bg-secondary)] border border-dashed border-[var(--border-default)] flex items-center justify-center text-[var(--text-muted)]">
                  <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 19.5h16.5a1.5 1.5 0 001.5-1.5V6a1.5 1.5 0 00-1.5-1.5H3.75A1.5 1.5 0 002.25 6v12a1.5 1.5 0 001.5 1.5z" />
                  </svg>
                </div>
              )}
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

              {/* Phase 56 — dietary/allergen chips (JSON arrays on the item) */}
              {(parseTags(item.dietary_info).length > 0 || parseTags(item.allergens).length > 0) && (
                <div className="flex flex-wrap gap-1 mb-3">
                  {parseTags(item.dietary_info).map((t) => (
                    <span
                      key={`d-${t}`}
                      className="px-1.5 py-0.5 text-[10px] font-medium rounded-full bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400"
                    >
                      {humanizeTag(t)}
                    </span>
                  ))}
                  {parseTags(item.allergens).map((t) => (
                    <span
                      key={`a-${t}`}
                      className="px-1.5 py-0.5 text-[10px] font-medium rounded-full bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"
                    >
                      {humanizeTag(t)} (allergen)
                    </span>
                  ))}
                </div>
              )}

              <div className="flex items-center gap-2 mb-3">
                <StatusBadge status={item.is_available ? "active" : "closed"} />
                <span className="text-xs text-[var(--text-muted)]">{item.preparation_time_minutes}min</span>
              </div>

              {canEdit && (
                <div className="flex flex-wrap gap-2 pt-2 border-t border-[var(--border-default)]">
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
                  {/* 48B — image management */}
                  <button
                    onClick={() => setImageItem(item)}
                    className="text-xs text-brand-700 dark:text-brand-400 hover:text-brand-600 font-medium"
                  >
                    {item.image_url ? "Replace Image" : "Add Image"}
                  </button>
                  {item.image_url && (
                    <button
                      onClick={() => setConfirmRemoveImage(item)}
                      className="text-xs text-red-600 hover:text-red-500 font-medium"
                    >
                      Remove Image
                    </button>
                  )}
                  {/* Phase 56 — soft delete (admin-only; backend-enforced) */}
                  {isAdmin && (
                    <button
                      onClick={() => setConfirmDelete(item)}
                      className="text-xs text-red-600 hover:text-red-500 font-medium"
                    >
                      Delete
                    </button>
                  )}
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

      {/* 48B — image upload modal (choose → preview → confirm → uploading) */}
      {imageItem && (
        <MenuItemImageModal
          cafeteriaId={selectedCafeteria}
          item={imageItem}
          onClose={() => setImageItem(null)}
          onSaved={async () => {
            setImageItem(null);
            await loadItems();
            toast("Image uploaded", "success");
          }}
        />
      )}

      {/* 48B — image removal confirmation */}
      {confirmRemoveImage && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          onClick={() => setConfirmRemoveImage(null)}
        >
          <div
            className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl shadow-xl w-full max-w-sm mx-4 p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-base font-semibold text-[var(--text-primary)] mb-2">
              Remove image from {confirmRemoveImage.name}?
            </h3>
            <p className="text-sm text-[var(--text-secondary)] mb-4">
              The menu item stays fully available — only its photo is removed.
              You can upload a new image at any time.
            </p>
            <div className="flex justify-end gap-2">
              <Button size="sm" variant="ghost" onClick={() => setConfirmRemoveImage(null)}>
                Cancel
              </Button>
              <Button size="sm" variant="danger" loading={removeImageLoading} onClick={handleConfirmRemoveImage}>
                Remove Image
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Phase 56 — copy previous day's daily menu (manager/admin) */}
      {showCopyDaily && (
        <CopyDailyMenuModal
          cafeteriaId={selectedCafeteria}
          onClose={() => setShowCopyDaily(false)}
          onCopied={() => {
            setShowCopyDaily(false);
            loadDailyMenu();
          }}
        />
      )}

      {/* Phase 56 — menu item deletion confirmation (soft delete) */}
      {confirmDelete && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          onClick={() => setConfirmDelete(null)}
        >
          <div
            className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl shadow-xl w-full max-w-sm mx-4 p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-base font-semibold text-[var(--text-primary)] mb-2">
              Delete {confirmDelete.name}?
            </h3>
            <p className="text-sm text-[var(--text-secondary)] mb-4">
              This removes the item from future menus and the active catalog.
              Historical orders and reports are unaffected — order history
              keeps the item name from its snapshot.
            </p>
            <div className="flex justify-end gap-2">
              <Button size="sm" variant="ghost" onClick={() => setConfirmDelete(null)}>
                Cancel
              </Button>
              <Button size="sm" variant="danger" loading={deleteLoading} onClick={handleDeleteMenuItem}>
                Delete Item
              </Button>
            </div>
          </div>
        </div>
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

      {/* WS4 — unpublish confirmation modal */}
      {confirmUnpublish && dailyMenu && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setConfirmUnpublish(false)}>
          <div
            className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl shadow-xl w-full max-w-sm mx-4 p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-base font-semibold text-[var(--text-primary)] mb-2">Unpublish Daily Menu?</h3>
            <p className="text-sm text-[var(--text-secondary)] mb-4">
              Students will no longer see today&apos;s menu for this cafeteria.
              The menu is archived and a replacement draft can be created.
            </p>
            <div className="flex justify-end gap-2">
              <Button size="sm" variant="ghost" onClick={() => setConfirmUnpublish(false)}>Cancel</Button>
              <Button size="sm" variant="danger" loading={dailyLoading} onClick={handleUnpublishDailyMenu}>
                Unpublish
              </Button>
            </div>
          </div>
        </div>
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
    // Phase 56 — dietary/allergen tags edited as toggle chips; persisted as
    // JSON array strings on the existing columns ("[]" clears them).
    dietary_tags: parseTags(item?.dietary_info),
    allergen_tags: parseTags(item?.allergens),
  });
  const [saving, setSaving] = useState(false);
  const { toast } = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      // Backend update semantics: None = no change — sending JSON strings
      // (including "[]") lets an edited item have its tags cleared.
      const { dietary_tags, allergen_tags, ...rest } = form;
      const payload = {
        ...rest,
        dietary_info: JSON.stringify(dietary_tags),
        allergens: JSON.stringify(allergen_tags),
      };
      if (item) {
        await updateMenuItem(cafeteriaId, item.id, {
          ...payload,
          price: form.price * 100,
        });
      } else {
        await createMenuItem(cafeteriaId, {
          ...payload,
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
          {/* Phase 56 — dietary/allergen toggle chips */}
          <div>
            <span className="block text-sm font-medium text-[var(--text-secondary)] mb-1">Dietary</span>
            <div className="flex flex-wrap gap-1.5">
              {DIETARY_TAGS.map((t) => {
                const on = form.dietary_tags.includes(t);
                return (
                  <button
                    key={t}
                    type="button"
                    onClick={() =>
                      setForm({
                        ...form,
                        dietary_tags: on
                          ? form.dietary_tags.filter((x) => x !== t)
                          : [...form.dietary_tags, t],
                      })
                    }
                    className={`px-2 py-1 text-xs font-medium rounded-full capitalize transition-colors ${
                      on
                        ? "bg-emerald-600 text-white"
                        : "bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:bg-emerald-50 dark:hover:bg-emerald-900/30"
                    }`}
                  >
                    {humanizeTag(t)}
                  </button>
                );
              })}
            </div>
          </div>
          <div>
            <span className="block text-sm font-medium text-[var(--text-secondary)] mb-1">Allergens</span>
            <div className="flex flex-wrap gap-1.5">
              {ALLERGEN_TAGS.map((t) => {
                const on = form.allergen_tags.includes(t);
                return (
                  <button
                    key={t}
                    type="button"
                    onClick={() =>
                      setForm({
                        ...form,
                        allergen_tags: on
                          ? form.allergen_tags.filter((x) => x !== t)
                          : [...form.allergen_tags, t],
                      })
                    }
                    className={`px-2 py-1 text-xs font-medium rounded-full capitalize transition-colors ${
                      on
                        ? "bg-amber-500 text-white"
                        : "bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:bg-amber-50 dark:hover:bg-amber-900/30"
                    }`}
                  >
                    {humanizeTag(t)}
                  </button>
                );
              })}
            </div>
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

/* Phase 56 — copy a previous day's daily menu into a NEW draft.
   Sources: non-archived menus (draft/published) on a past date with at
   least one item. The backend rejects same-day copies (400) and occupied
   target dates (409) — this modal never silently overwrites an existing
   menu; the conflict message tells the user what to do instead. */
function CopyDailyMenuModal({
  cafeteriaId,
  onClose,
  onCopied,
}: {
  cafeteriaId: string;
  onClose: () => void;
  onCopied: () => void;
}) {
  const [sources, setSources] = useState<DailyMenu[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadErr, setLoadErr] = useState<ApiErrorInfo | null>(null);
  const [sourceId, setSourceId] = useState("");
  const [targetDate, setTargetDate] = useState(isoDate(new Date(Date.now() + 86400000)));
  const [submitting, setSubmitting] = useState(false);
  const [copied, setCopied] = useState<{ menu_date: string; count: number } | null>(null);
  const { toast } = useToast();

  const loadSources = useCallback(async () => {
    setLoading(true);
    setLoadErr(null);
    try {
      const data = await getDailyMenus(cafeteriaId);
      const today = isoDate(new Date());
      // Copy candidates: past-dated, non-archived menus that carry items.
      const list = (data.menus ?? [])
        .filter(
          (m: DailyMenu) =>
            m.status !== "archived" &&
            m.menu_date < today &&
            (m.items?.length ?? 0) > 0,
        )
        .sort((a: DailyMenu, b: DailyMenu) => b.menu_date.localeCompare(a.menu_date));
      setSources(list);
      setSourceId((prev) => prev || list[0]?.id || "");
    } catch (err) {
      setLoadErr(getApiErrorInfo(err));
    } finally {
      setLoading(false);
    }
  }, [cafeteriaId]);

  useEffect(() => { loadSources(); }, [loadSources]);

  const source = sources.find((m) => m.id === sourceId) ?? null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!source || !targetDate) return;
    setSubmitting(true);
    try {
      const menu = await copyDailyMenu(cafeteriaId, {
        source_date: source.menu_date,
        target_date: targetDate,
      });
      setCopied({ menu_date: menu.menu_date, count: (menu.items ?? []).length });
    } catch (err) {
      // e.g. 409 "target date already has a PUBLISHED menu — unpublish it
      // first or choose another date" — surfaced verbatim, nothing overwritten.
      toast(getApiErrorInfo(err).message, "error");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl shadow-xl w-full max-w-md mx-4 p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-4">
          Copy Previous Day&apos;s Menu
        </h2>
        {copied ? (
          <div className="space-y-4">
            <p className="text-sm text-emerald-700 dark:text-emerald-400">
              Draft created for {copied.menu_date} with {copied.count} item{copied.count === 1 ? "" : "s"}.
            </p>
            <p className="text-xs text-[var(--text-muted)]">
              This is a new draft — publish it from the daily-menu tools when ready.
              Existing menus on the target date were not touched.
            </p>
            <div className="flex justify-end">
              <Button
                size="sm"
                onClick={() => {
                  setCopied(null);
                  onCopied();
                }}
              >
                Done
              </Button>
            </div>
          </div>
        ) : loadErr ? (
          <LoadErrorState error={loadErr} subject="previous daily menus" onRetry={() => loadSources()} />
        ) : loading ? (
          <p className="text-sm text-[var(--text-muted)]">Loading previous menus…</p>
        ) : sources.length === 0 ? (
          <EmptyState
            title="No previous menus"
            description="Only non-archived menus from a previous date with at least one item can be copied."
          />
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1">
                Source (previous menu)
              </label>
              <select
                value={sourceId}
                onChange={(e) => setSourceId(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)]"
                required
              >
                <option value="">Select a menu…</option>
                {sources.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.menu_date} — {m.status} ({m.items.length} item{m.items.length === 1 ? "" : "s"})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1">
                Target date (new draft)
              </label>
              <input
                type="date"
                value={targetDate}
                min={isoDate(new Date())}
                onChange={(e) => setTargetDate(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)]"
                required
              />
            </div>
            {source && (
              <div className="bg-[var(--bg-secondary)] rounded-lg p-3 text-xs text-[var(--text-secondary)]">
                {source.menu_date} ({source.items.length} item{source.items.length === 1 ? "" : "s"}) → new draft on {targetDate || "…"}.
                Prices, ordering and availability carry over; inactive menu items are skipped.
              </div>
            )}
            <div className="flex gap-2 justify-end pt-2">
              <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
              <Button
                type="submit"
                loading={submitting}
                disabled={!sourceId || !targetDate || targetDate === source?.menu_date}
              >
                Copy Menu
              </Button>
            </div>
          </form>
        )}
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
                    {m.name} — {formatPricePKR(m.price)}
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

/* 48B — menu item image modal: choose file → local preview → confirm →
   uploading → success (parent closes modal + refreshes, Phase 47 lesson).
   Upload is NEVER automatic on file selection; the client previews locally
   and the confirm button triggers the raw-binary upload.

   Constraints mirrored from the backend (authoritative there):
   - JPEG / PNG / WebP only (magic bytes checked server-side)
   - 5MB maximum
   Raw-binary upload because the deployment does not ship python-multipart;
   the File body is sent as-is with its image/* Content-Type. */
const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
const ACCEPTED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];

function MenuItemImageModal({
  cafeteriaId,
  item,
  onClose,
  onSaved,
}: {
  cafeteriaId: string;
  item: MenuItem;
  onClose: () => void;
  onSaved: () => Promise<void> | void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<ApiErrorInfo | null>(null);
  const { toast } = useToast();

  // Release the object URL when the modal closes or the file changes.
  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const chosen = e.target.files?.[0];
    if (!chosen) return;
    // Client-side guard — the backend re-validates authoritatively.
    if (!ACCEPTED_IMAGE_TYPES.includes(chosen.type)) {
      toast("Unsupported image type. Choose a JPEG, PNG or WebP file.", "error");
      return;
    }
    if (chosen.size > MAX_IMAGE_BYTES) {
      toast("Image must be 5MB or smaller.", "error");
      return;
    }
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setFile(chosen);
    setPreviewUrl(URL.createObjectURL(chosen));
    setError(null);
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      await uploadMenuItemImage(cafeteriaId, item.id, file);
      // Success → parent closes the modal and refreshes the grid.
      await onSaved();
    } catch (err) {
      // Keep the modal open; surface the structured error (Phase 46).
      setError(getApiErrorInfo(err));
      setUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl shadow-xl w-full max-w-md mx-4 p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-1">
          {item.image_url ? "Replace Image" : "Add Image"} — {item.name}
        </h2>
        <p className="text-xs text-[var(--text-muted)] mb-4">
          JPEG, PNG or WebP — up to 5MB. The image is uploaded only after you
          confirm.
        </p>

        {item.image_url && !file && (
          <div className="mb-4">
            <p className="text-xs font-medium text-[var(--text-secondary)] mb-1">Current image</p>
            <img
              src={resolveApiImageUrl(item.image_url) as string}
              alt={item.name}
              className="w-full h-40 object-cover rounded-lg border border-[var(--border-default)]"
            />
          </div>
        )}

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1">
              Choose file
            </label>
            <input
              type="file"
              accept={ACCEPTED_IMAGE_TYPES.join(",")}
              onChange={handleFileChange}
              className="block w-full text-sm text-[var(--text-secondary)] file:mr-3 file:px-3 file:py-1.5 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-brand-50 file:text-brand-700 dark:file:bg-brand-900/30 dark:file:text-brand-300 hover:file:bg-brand-100 dark:hover:file:bg-brand-900/50"
            />
          </div>

          {previewUrl && (
            <div>
              <p className="text-xs font-medium text-[var(--text-secondary)] mb-1">
                Preview — {file?.name} ({Math.max(1, Math.round((file?.size ?? 0) / 1024))} KB)
              </p>
              <img
                src={previewUrl}
                alt="Preview"
                className="w-full h-40 object-cover rounded-lg border border-[var(--border-default)]"
              />
            </div>
          )}

          {error && (
            <div className="text-xs text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/10 border border-red-200 dark:border-red-800 rounded-lg p-3">
              {error.message}
            </div>
          )}

          <div className="flex gap-2 justify-end pt-2">
            <Button type="button" variant="ghost" onClick={onClose} disabled={uploading}>
              Cancel
            </Button>
            <Button
              type="button"
              loading={uploading}
              disabled={!file}
              onClick={handleUpload}
            >
              {item.image_url ? "Replace Image" : "Upload Image"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
