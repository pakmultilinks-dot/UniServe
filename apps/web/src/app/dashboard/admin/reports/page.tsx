"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import {
  getSalesReport,
  getDailySalesReport,
  getSalesByCafeteriaReport,
  getOrderSummaryReport,
  getOrderVolumeReport,
  getCancellationRateReport,
  getPopularItemsReport,
  getCafeteriaPerformanceReport,
  getInventoryStockLevelsReport,
  getInventoryLowStockReport,
  getInventoryTurnoverReport,
  getCafeteriaPeakHoursReport,
  getCafeterias,
  getMyCafeterias,
  ApiClientError,
  getApiErrorInfo,
} from "@/lib/api";
import type { ApiErrorInfo, SalesReportSummary } from "@/lib/api";
import { PageHeader } from "@/components/ui/PageHeader";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadErrorState } from "@/components/ui/LoadErrorState";
import type {
  Cafeteria,
  CafeteriaPeakHoursResponse,
  CafeteriaPerformanceResponse,
  CafeteriaSalesRow,
  CancellationRateResponse,
  DailySalesRow,
  InventoryLowStockResponse,
  InventoryStockLevelsResponse,
  InventoryTurnoverResponse,
  OrderSummaryResponse,
  OrderStatusBreakdown,
  OrderVolumeResponse,
  PopularItemRow,
} from "@uniserve/shared-types";

// ---------------------------------------------------------------------------
// Date + formatting helpers (local calendar dates, backend contract YYYY-MM-DD)
// ---------------------------------------------------------------------------

const toISO = (d: Date): string => {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
};

const addDays = (d: Date, n: number): Date =>
  new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);

const formatCurrency = (amount: number): string =>
  `Rs. ${(amount / 100).toLocaleString("en-PK", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;

const formatPct = (rate: number): string => `${(rate * 100).toFixed(1)}%`;

const shortDate = (iso: string): string =>
  new Date(`${iso}T00:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric" });

type DatePreset = "today" | "7d" | "30d" | "custom";

interface DateRange {
  start: string;
  end: string;
}

function presetRange(preset: DatePreset, customStart: string, customEnd: string): DateRange {
  const today = new Date();
  const todayISO = toISO(today);
  if (preset === "today") return { start: todayISO, end: todayISO };
  if (preset === "7d") return { start: toISO(addDays(today, -6)), end: todayISO };
  if (preset === "30d") return { start: toISO(addDays(today, -29)), end: todayISO };
  return { start: customStart, end: customEnd };
}

// Filter selections persist across reloads (same tab). Restore is validated so
// a stale cafeteria id or hand-edited value falls back to safe defaults.
const FILTERS_STORAGE_KEY = "uniserve.admin.reports.filters";

interface StoredFilters {
  preset: DatePreset;
  cafeteria: string;
  customStart: string;
  customEnd: string;
}

function loadStoredFilters(): StoredFilters | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(FILTERS_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<StoredFilters> | null;
    if (!parsed || typeof parsed !== "object") return null;
    const preset = parsed.preset;
    if (preset !== "today" && preset !== "7d" && preset !== "30d" && preset !== "custom") {
      return null;
    }
    const customStart = typeof parsed.customStart === "string" ? parsed.customStart : "";
    const customEnd = typeof parsed.customEnd === "string" ? parsed.customEnd : "";
    if (preset === "custom" && (!customStart || !customEnd || customStart > customEnd)) {
      return null;
    }
    return {
      preset,
      cafeteria: typeof parsed.cafeteria === "string" ? parsed.cafeteria : "",
      customStart,
      customEnd,
    };
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Presentational chart primitives (no chart dependency — Phase 49 constraint)
// ---------------------------------------------------------------------------

interface TrendPoint {
  label: string;
  value: number;
  secondary?: number;
}

function TrendChart({ points, height = 130 }: { points: TrendPoint[]; height?: number }) {
  if (points.length === 0) return null;
  const max = Math.max(1, ...points.map((p) => Math.max(p.value, p.secondary ?? 0)));
  const plotH = height - 16;
  const slot = 10;
  return (
    <div className="w-full">
      <svg
        viewBox={`0 0 ${points.length * slot} ${plotH}`}
        className="w-full"
        style={{ height: plotH }}
        preserveAspectRatio="none"
        role="img"
        aria-label="Trend chart"
      >
        {points.map((p, i) => {
          const h1 = p.value > 0 ? Math.max((p.value / max) * (plotH - 4), 2) : 0;
          const h2 =
            p.secondary !== undefined && p.secondary > 0
              ? Math.max((p.secondary / max) * (plotH - 4), 2)
              : 0;
          return (
            <g key={`${p.label}-${i}`}>
              <rect
                x={i * slot + 1}
                y={plotH - h1}
                width={slot - 2}
                height={h1}
                rx={1}
                className="fill-brand-600"
                opacity={0.4}
              >
                <title>{`${p.label}: ${p.value.toLocaleString()}`}</title>
              </rect>
              {p.secondary !== undefined && (
                <rect
                  x={i * slot + 3}
                  y={plotH - h2}
                  width={slot - 6}
                  height={h2}
                  rx={1}
                  className="fill-brand-600"
                >
                  <title>{`${p.label} completed: ${p.secondary.toLocaleString()}`}</title>
                </rect>
              )}
            </g>
          );
        })}
      </svg>
      <div className="flex justify-between text-[10px] text-[var(--text-muted)] mt-1">
        <span>{points[0]?.label}</span>
        {points.length > 2 && <span>{points[Math.floor(points.length / 2)]?.label}</span>}
        <span>{points[points.length - 1]?.label}</span>
      </div>
    </div>
  );
}

function HourlyStrip({ hours }: { hours: { hour: number; order_count: number }[] }) {
  const map = new Map(hours.map((h) => [h.hour, h.order_count]));
  const max = Math.max(1, ...hours.map((h) => h.order_count));
  return (
    <div className="flex items-end gap-[3px] h-24">
      {Array.from({ length: 24 }, (_, hour) => {
        const v = map.get(hour) ?? 0;
        return (
          <div
            key={hour}
            className="flex-1 flex flex-col justify-end items-center"
            title={`${String(hour).padStart(2, "0")}:00 — ${v} order${v === 1 ? "" : "s"}`}
          >
            <div
              className="w-full bg-brand-600 rounded-t"
              style={{
                height: `${(v / max) * 72}px`,
                minHeight: v > 0 ? 2 : 0,
                opacity: v > 0 ? 1 : 0.12,
              }}
            />
            <span className="text-[9px] text-[var(--text-muted)] mt-1 h-3">
              {hour % 3 === 0 ? String(hour).padStart(2, "0") : ""}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function StatusBars({ breakdown, total }: { breakdown: OrderStatusBreakdown; total: number }) {
  const rows = [
    { label: "Pending", value: breakdown.pending, bar: "bg-amber-400" },
    { label: "Preparing", value: breakdown.preparing, bar: "bg-blue-400" },
    { label: "Ready", value: breakdown.ready, bar: "bg-indigo-400" },
    { label: "Completed", value: breakdown.completed, bar: "bg-green-500" },
    { label: "Cancelled", value: breakdown.cancelled, bar: "bg-red-400" },
  ];
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <div className="space-y-2">
      {rows.map((r) => (
        <div key={r.label} className="flex items-center gap-3">
          <span className="w-20 text-xs text-[var(--text-secondary)] shrink-0">{r.label}</span>
          <div className="flex-1 h-3 bg-[var(--bg-secondary)] rounded overflow-hidden">
            <div
              className={`h-full rounded ${r.bar}`}
              style={{ width: `${(r.value / max) * 100}%` }}
            />
          </div>
          <span className="w-24 text-xs text-[var(--text-secondary)] text-right shrink-0">
            {r.value.toLocaleString()}
            {total > 0 && (
              <span className="text-[var(--text-muted)]"> ({((r.value / total) * 100).toFixed(0)}%)</span>
            )}
          </span>
        </div>
      ))}
    </div>
  );
}

function Section({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl p-5 shadow-card">
      <h3 className="text-sm font-semibold text-[var(--text-primary)]">{title}</h3>
      {subtitle && <p className="text-xs text-[var(--text-muted)] mt-0.5">{subtitle}</p>}
      <div className="mt-4">{children}</div>
    </div>
  );
}

function StatTile({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="bg-[var(--bg-secondary)] border border-[var(--border-default)] rounded-lg p-3">
      <p className="text-[11px] font-medium text-[var(--text-muted)] uppercase">{label}</p>
      <p className="text-lg font-bold text-[var(--text-primary)] mt-0.5">{value}</p>
      {hint && <p className="text-[10px] text-[var(--text-muted)] mt-0.5">{hint}</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Top-item merge (All Cafeterias view) — backend rows are authoritative;
// merging sums the same menu item across cafeterias (presentational only).
// ---------------------------------------------------------------------------

interface MergedPopularItem {
  menu_item_id: string | null;
  item_name: string;
  total_quantity: number;
  total_revenue: number;
  order_count: number;
  cafeterias: string[];
}

function mergePopularItems(
  perCafeteria: { cafeteriaName: string; items: PopularItemRow[] }[],
): MergedPopularItem[] {
  const byId = new Map<string, MergedPopularItem>();
  for (const { cafeteriaName, items } of perCafeteria) {
    for (const it of items) {
      const key = it.menu_item_id ?? it.item_name;
      const existing = byId.get(key);
      if (existing) {
        existing.total_quantity += it.total_quantity;
        existing.total_revenue += it.total_revenue;
        existing.order_count += it.order_count;
        if (!existing.cafeterias.includes(cafeteriaName)) existing.cafeterias.push(cafeteriaName);
      } else {
        byId.set(key, {
          menu_item_id: it.menu_item_id,
          item_name: it.item_name,
          total_quantity: it.total_quantity,
          total_revenue: it.total_revenue,
          order_count: it.order_count,
          cafeterias: [cafeteriaName],
        });
      }
    }
  }
  return Array.from(byId.values()).sort((a, b) => b.total_quantity - a.total_quantity);
}

// Zero-fill missing days for a readable time axis (presentation only).
function zeroFillDays(rows: DailySalesRow[], start: string, end: string): DailySalesRow[] {
  const byDate = new Map(rows.map((r) => [r.date, r]));
  const out: DailySalesRow[] = [];
  let cur = new Date(`${start}T00:00:00`);
  const last = new Date(`${end}T00:00:00`);
  let guard = 0;
  while (cur <= last && guard < 400) {
    const iso = toISO(cur);
    out.push(byDate.get(iso) ?? { date: iso, revenue: 0, order_count: 0 });
    cur = addDays(cur, 1);
    guard += 1;
  }
  return out;
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

interface LoadedReport {
  sales: SalesReportSummary;
  orderSummary: OrderSummaryResponse;
  dailyRows: DailySalesRow[];
  volume: OrderVolumeResponse;
  cancellation: CancellationRateResponse;
  byCafeteria: CafeteriaSalesRow[] | null;
  performance: CafeteriaPerformanceResponse | null;
  popular: MergedPopularItem[];
  /** Phase 58 (Workstream C) — cafeteria-scoped inventory + peak-hour
      reports. Null when "All Cafeterias" is selected (admin view): these
      four backend endpoints require a specific cafeteria. */
  inventory: {
    stockLevels: InventoryStockLevelsResponse;
    lowStock: InventoryLowStockResponse;
    turnover: InventoryTurnoverResponse;
    peakHours: CafeteriaPeakHoursResponse;
  } | null;
}

export default function ReportsPage() {
  const { user } = useAuth();
  const router = useRouter();
  const isAdmin = user?.role === "university_admin";
  const isManager = user?.role === "cafeteria_manager";

  const [cafeterias, setCafeterias] = useState<Cafeteria[]>([]);
  const [selectedCafeteria, setSelectedCafeteria] = useState(""); // "" = All Cafeterias (admin)
  const [datePreset, setDatePreset] = useState<DatePreset>(
    () => loadStoredFilters()?.preset ?? "7d",
  );
  const [customStart, setCustomStart] = useState(
    () => loadStoredFilters()?.customStart || toISO(addDays(new Date(), -6)),
  );
  const [customEnd, setCustomEnd] = useState(
    () => loadStoredFilters()?.customEnd || toISO(new Date()),
  );

  const [report, setReport] = useState<LoadedReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [accessError, setAccessError] = useState<string | null>(null);
  const [cafeteriasError, setCafeteriasError] = useState<ApiErrorInfo | null>(null);
  const [loadError, setLoadError] = useState<ApiErrorInfo | null>(null);
  /** Phase 58 (Workstream C) — inventory/peak-hour report failures render as
      their own inline error state; they must never masquerade as "no data". */
  const [inventoryReportsError, setInventoryReportsError] = useState<ApiErrorInfo | null>(null);
  const [cafReloadKey, setCafReloadKey] = useState(0);
  const [reloadKey, setReloadKey] = useState(0);

  /* Race-condition guard: only the latest request may set state. */
  const requestSeq = useRef(0);
  /* Filter persistence must not clobber storage before restore has read it. */
  const filtersRestored = useRef(false);

  // -- Cafeteria selector data (manager stays scoped to assigned) -----------
  useEffect(() => {
    if (user && !isAdmin && !isManager) {
      router.push("/dashboard");
      return;
    }
    if (!isAdmin && !isManager) return;
    getCafeterias()
      .then(async (data) => {
        let visible = data;
        if (isManager && !isAdmin) {
          const assigned = await getMyCafeterias();
          if (assigned.length > 0) {
            visible = data.filter((c) => assigned.includes(c.id));
          }
        }
        setCafeterias(visible);
        setCafeteriasError(null);
        // Restore the previous cafeteria selection when it is still visible;
        // otherwise admin defaults to All Cafeterias, manager to their single one.
        const stored = loadStoredFilters();
        const restored =
          stored && visible.some((c) => c.id === stored.cafeteria) ? stored.cafeteria : "";
        if (isAdmin) setSelectedCafeteria((cur) => cur || restored || "");
        else setSelectedCafeteria((cur) => cur || restored || visible[0]?.id || "");
        filtersRestored.current = true;
      })
      .catch((err) => {
        setCafeteriasError(getApiErrorInfo(err));
        setLoading(false);
      });
  }, [user, isAdmin, isManager, router, cafReloadKey]);

  // -- Report data (all endpoints follow the active filters) ----------------
  useEffect(() => {
    if (!user || (!isAdmin && !isManager)) return;
    if (cafeteriasError) return;
    if (datePreset === "custom" && (!customStart || !customEnd || customStart > customEnd)) {
      return; // invalid custom range — keep previous data, hint shown below
    }

    const reqId = ++requestSeq.current;
    setLoading(true);

    const { start, end } = presetRange(datePreset, customStart, customEnd);
    const scope = selectedCafeteria || undefined; // undefined = all / backend default
    const range = { start_date: start, end_date: end };

    (async () => {
      try {
        const [sales, orderSummary, dailySales, volume, cancellation] = await Promise.all([
          getSalesReport({ ...range, cafeteria_id: scope }),
          getOrderSummaryReport({ ...range, cafeteria_id: scope }),
          getDailySalesReport({ ...range, cafeteria_id: scope }),
          getOrderVolumeReport({ ...range, cafeteria_id: scope }),
          getCancellationRateReport({ ...range, cafeteria_id: scope }),
        ]);

        let byCafeteria: CafeteriaSalesRow[] | null = null;
        let performance: CafeteriaPerformanceResponse | null = null;
        let popular: MergedPopularItem[] = [];
        let inventory: LoadedReport["inventory"] = null;
        let inventoryError: ApiErrorInfo | null = null;

        if (selectedCafeteria) {
          // Specific cafeteria: performance panel + its top items.
          const [perf, pop] = await Promise.all([
            getCafeteriaPerformanceReport(selectedCafeteria, range),
            getPopularItemsReport(selectedCafeteria, { ...range, limit: 10 }),
          ]);
          performance = perf;
          popular = mergePopularItems([
            {
              cafeteriaName: cafeterias.find((c) => c.id === selectedCafeteria)?.name ?? "Cafeteria",
              items: pop.items,
            },
          ]);
          // Phase 58 (Workstream C) — the four previously unwired endpoints.
          // Fetched independently so a failure here never blanks the core
          // report above (rendered as its own inline error state instead).
          try {
            const [stockLevels, lowStock, turnover, peakHours] = await Promise.all([
              getInventoryStockLevelsReport(selectedCafeteria),
              getInventoryLowStockReport(selectedCafeteria),
              getInventoryTurnoverReport(selectedCafeteria, range),
              getCafeteriaPeakHoursReport(selectedCafeteria, range),
            ]);
            inventory = { stockLevels, lowStock, turnover, peakHours };
          } catch (err) {
            inventory = null;
            // getApiErrorInfo already maps 403 → a safe permission message
            // that surfaces the backend authorization error verbatim.
            inventoryError = getApiErrorInfo(err);
          }
        } else if (isAdmin) {
          // All Cafeterias (admin only): cross-cafeteria table + merged top items.
          const byCaf = await getSalesByCafeteriaReport(range);
          byCafeteria = byCaf.rows;
          const perCaf = await Promise.all(
            cafeterias.map(async (c) => {
              try {
                const pop = await getPopularItemsReport(c.id, { ...range, limit: 50 });
                return { cafeteriaName: c.name, items: pop.items };
              } catch {
                return { cafeteriaName: c.name, items: [] as PopularItemRow[] };
              }
            }),
          );
          popular = mergePopularItems(perCaf).slice(0, 10);
        }

        if (reqId !== requestSeq.current) return; // stale response — discard
        setReport({
          sales,
          orderSummary,
          dailyRows: dailySales.rows,
          volume,
          cancellation,
          byCafeteria,
          performance,
          popular,
          inventory,
        });
        setInventoryReportsError(inventoryError);
        setAccessError(null);
        setLoadError(null);
      } catch (err) {
        if (reqId !== requestSeq.current) return;
        setReport(null);
        if (err instanceof ApiClientError && err.status === 403) {
          setAccessError(
            err.message || "You do not have access to this cafeteria's reports.",
          );
          setLoadError(null);
        } else {
          setAccessError(null);
          setLoadError(getApiErrorInfo(err));
        }
      } finally {
        if (reqId === requestSeq.current) setLoading(false);
      }
    })();
  }, [
    user,
    isAdmin,
    isManager,
    selectedCafeteria,
    datePreset,
    customStart,
    customEnd,
    cafeterias,
    cafeteriasError,
    reloadKey,
  ]);

  // Persist filter selections across reloads (restore is validated on load).
  useEffect(() => {
    if (!filtersRestored.current) return; // do not clobber storage pre-restore
    try {
      window.sessionStorage.setItem(
        FILTERS_STORAGE_KEY,
        JSON.stringify({
          preset: datePreset,
          cafeteria: selectedCafeteria,
          customStart,
          customEnd,
        }),
      );
    } catch {
      /* storage unavailable — filters simply do not persist */
    }
  }, [datePreset, selectedCafeteria, customStart, customEnd]);

  const customInvalid =
    datePreset === "custom" && (!customStart || !customEnd || customStart > customEnd);

  const range = useMemo(
    () => presetRange(datePreset, customStart, customEnd),
    [datePreset, customStart, customEnd],
  );
  const rangeLabel = `${shortDate(range.start)} – ${shortDate(range.end)}`;
  const cafeteriaLabel = selectedCafeteria
    ? cafeterias.find((c) => c.id === selectedCafeteria)?.name ?? "Selected cafeteria"
    : "All Cafeterias";

  // Trend points: zero-filled day axis, revenue from sales/daily.
  const revenuePoints: TrendPoint[] = useMemo(() => {
    if (!report) return [];
    return zeroFillDays(report.dailyRows, range.start, range.end).map((r) => ({
      label: shortDate(r.date),
      value: r.revenue,
    }));
  }, [report, range.start, range.end]);

  const orderPoints: TrendPoint[] = useMemo(() => {
    if (!report) return [];
    const byDate = new Map(report.volume.daily.map((d) => [d.date, d]));
    const days = zeroFillDays([], range.start, range.end);
    return days.map((d) => {
      const row = byDate.get(d.date);
      return {
        label: shortDate(d.date),
        value: row?.order_count ?? 0,
        secondary: row?.completed_count ?? 0,
      };
    });
  }, [report, range.start, range.end]);

  // Daily detail table — merged from volume.daily + sales.daily by date.
  const dailyTable = useMemo(() => {
    if (!report) return [];
    const salesByDate = new Map(report.dailyRows.map((r) => [r.date, r]));
    return zeroFillDays([], range.start, range.end)
      .map((d) => {
        const vol = report.volume.daily.find((v) => v.date === d.date);
        const sale = salesByDate.get(d.date);
        return {
          date: d.date,
          order_count: vol?.order_count ?? 0,
          completed: vol?.completed_count ?? 0,
          cancelled: vol?.cancelled_count ?? 0,
          revenue: sale?.revenue ?? 0,
        };
      })
      .filter((r) => r.order_count > 0 || r.revenue > 0)
      .reverse();
  }, [report, range.start, range.end]);

  if (!user || (!isAdmin && !isManager)) return null;

  const hasAnyData =
    !!report && (report.orderSummary.total_orders > 0 || report.sales.total_orders > 0);

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Reports & Analytics"
        description="Order, revenue, and cafeteria analytics from live backend data"
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={selectedCafeteria}
              onChange={(e) => setSelectedCafeteria(e.target.value)}
              aria-label="Cafeteria filter"
              className="px-3 py-2 text-sm border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)]"
            >
              {isAdmin && <option value="">All Cafeterias</option>}
              {cafeterias.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
            <div className="flex rounded-lg border border-[var(--border-default)] overflow-hidden">
              {(
                [
                  ["today", "Today"],
                  ["7d", "7 Days"],
                  ["30d", "30 Days"],
                  ["custom", "Custom"],
                ] as const
              ).map(([key, label]) => (
                <button
                  key={key}
                  onClick={() => setDatePreset(key)}
                  className={`px-3 py-2 text-xs font-medium transition-colors ${
                    datePreset === key
                      ? "bg-brand-600 text-white"
                      : "bg-[var(--bg-primary)] text-[var(--text-secondary)] hover:bg-[var(--bg-secondary)]"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
            <button
              onClick={() => setReloadKey((k) => k + 1)}
              className="px-3 py-2 text-xs font-medium border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-secondary)] hover:bg-[var(--bg-secondary)] transition-colors"
            >
              Refresh
            </button>
          </div>
        }
      />

      {/* Custom range inputs + active-filter indicator */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        {datePreset === "custom" && (
          <div className="flex items-center gap-2 text-sm">
            <input
              type="date"
              value={customStart}
              max={customEnd || undefined}
              onChange={(e) => setCustomStart(e.target.value)}
              aria-label="Custom start date"
              className="px-2 py-1.5 text-xs border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)]"
            />
            <span className="text-[var(--text-muted)]">to</span>
            <input
              type="date"
              value={customEnd}
              min={customStart || undefined}
              onChange={(e) => setCustomEnd(e.target.value)}
              aria-label="Custom end date"
              className="px-2 py-1.5 text-xs border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)]"
            />
          </div>
        )}
        <p className="text-xs text-[var(--text-muted)]">
          Showing <span className="font-medium text-[var(--text-secondary)]">{cafeteriaLabel}</span>
          {" · "}
          <span className="font-medium text-[var(--text-secondary)]">{rangeLabel}</span>
        </p>
        {customInvalid && (
          <p className="text-xs text-amber-700 dark:text-amber-400">
            Start date must be on or before end date.
          </p>
        )}
      </div>

      {cafeteriasError ? (
        <LoadErrorState
          error={cafeteriasError}
          subject="cafeterias"
          onRetry={() => setCafReloadKey((k) => k + 1)}
        />
      ) : loading ? (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
              <div
                key={i}
                className="h-24 bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl skeleton"
              />
            ))}
          </div>
          <div className="h-40 bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl skeleton mb-6" />
        </>
      ) : accessError ? (
        <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl p-6 text-center mb-6">
          <p className="text-sm font-semibold text-amber-800 dark:text-amber-300">
            You don&apos;t have access to this cafeteria&apos;s reports
          </p>
          <p className="text-xs text-amber-700 dark:text-amber-400 mt-1 max-w-md mx-auto">
            {accessError}
          </p>
          <p className="text-xs text-amber-700 dark:text-amber-400 mt-2">
            Manager reports are scoped to your assigned cafeteria.
          </p>
        </div>
      ) : loadError ? (
        <LoadErrorState
          error={loadError}
          subject="report"
          onRetry={() => setReloadKey((k) => k + 1)}
        />
      ) : !report || !hasAnyData ? (
        <EmptyState
          title="No orders found for this period"
          description="Try a wider date range or another cafeteria. Sales data will appear here once orders exist."
          icon={
            <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
            </svg>
          }
        />
      ) : (
        <>
          {/* KPI cards — every value sourced from a backend report endpoint */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl p-4 shadow-card">
              <p className="text-xs font-medium text-[var(--text-muted)] uppercase">Total Orders</p>
              <p className="text-2xl font-bold text-[var(--text-primary)] mt-1">
                {report.orderSummary.total_orders.toLocaleString()}
              </p>
            </div>
            <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl p-4 shadow-card">
              <p className="text-xs font-medium text-[var(--text-muted)] uppercase">Completed</p>
              <p className="text-2xl font-bold text-green-600 dark:text-green-400 mt-1">
                {report.orderSummary.status_breakdown.completed.toLocaleString()}
              </p>
            </div>
            <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl p-4 shadow-card">
              <p className="text-xs font-medium text-[var(--text-muted)] uppercase">Cancelled</p>
              <p className="text-2xl font-bold text-red-600 dark:text-red-400 mt-1">
                {report.orderSummary.status_breakdown.cancelled.toLocaleString()}
              </p>
            </div>
            <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl p-4 shadow-card">
              <p className="text-xs font-medium text-[var(--text-muted)] uppercase">Revenue</p>
              <p className="text-2xl font-bold text-green-600 dark:text-green-400 mt-1">
                {formatCurrency(report.sales.total_revenue)}
              </p>
            </div>
            <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl p-4 shadow-card">
              <p className="text-xs font-medium text-[var(--text-muted)] uppercase">Net Revenue</p>
              <p className="text-2xl font-bold text-green-600 dark:text-green-400 mt-1">
                {formatCurrency(report.sales.net_revenue)}
              </p>
              <p className="text-[10px] text-[var(--text-muted)] mt-1">
                {formatCurrency(report.sales.total_refunded)} refunded in period
              </p>
            </div>
            <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl p-4 shadow-card">
              <p className="text-xs font-medium text-[var(--text-muted)] uppercase">Avg Order Value</p>
              <p className="text-2xl font-bold text-[var(--text-primary)] mt-1">
                {formatCurrency(
                  report.sales.total_orders > 0
                    ? Math.round(report.sales.total_revenue / report.sales.total_orders)
                    : 0,
                )}
              </p>
              <p className="text-[10px] text-[var(--text-muted)] mt-1">per paid order</p>
            </div>
            <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl p-4 shadow-card">
              <p className="text-xs font-medium text-[var(--text-muted)] uppercase">Online Paid</p>
              <p className="text-2xl font-bold text-[var(--text-primary)] mt-1">
                {formatCurrency(report.sales.online_payment_volume ?? 0)}
              </p>
              <p className="text-[10px] text-[var(--text-muted)] mt-1">succeeded payments</p>
            </div>
            <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl p-4 shadow-card">
              <p className="text-xs font-medium text-[var(--text-muted)] uppercase">Cash Paid</p>
              <p className="text-2xl font-bold text-[var(--text-primary)] mt-1">
                {formatCurrency(report.sales.cash_payment_volume ?? 0)}
              </p>
              <p className="text-[10px] text-[var(--text-muted)] mt-1">succeeded payments</p>
            </div>
          </div>

          {/* Trend charts */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
            <Section title="Revenue by Day" subtitle={`Succeeded payment revenue · ${rangeLabel}`}>
              <TrendChart points={revenuePoints} />
            </Section>
            <Section
              title="Order Volume by Day"
              subtitle={`All orders (light) with completed orders (dark) · ${rangeLabel}`}
            >
              <TrendChart points={orderPoints} />
            </Section>
          </div>

          {/* Cafeteria performance — All view (admin) vs single cafeteria panel */}
          {selectedCafeteria === "" && isAdmin && (
            <div className="mb-6">
              <Section
                title="Cafeteria Performance"
                subtitle="Cross-cafeteria comparison for the selected period"
              >
                {report.byCafeteria && report.byCafeteria.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-left text-xs text-[var(--text-muted)] border-b border-[var(--border-default)]">
                          <th className="py-2 pr-4 font-medium">Cafeteria</th>
                          <th className="py-2 pr-4 font-medium text-right">Orders</th>
                          <th className="py-2 pr-4 font-medium text-right">Revenue</th>
                          <th className="py-2 pr-4 font-medium text-right">Completed</th>
                          <th className="py-2 pr-4 font-medium text-right">Cancelled</th>
                          <th className="py-2 pr-4 font-medium text-right">Refunded</th>
                          <th className="py-2 font-medium text-right">Avg Order Value</th>
                        </tr>
                      </thead>
                      <tbody>
                        {report.byCafeteria.map((row) => (
                          <tr
                            key={row.cafeteria_id}
                            className="border-b border-[var(--border-default)] last:border-0"
                          >
                            <td className="py-2.5 pr-4 font-medium text-[var(--text-primary)]">
                              {row.cafeteria_name}
                            </td>
                            <td className="py-2.5 pr-4 text-right text-[var(--text-secondary)]">
                              {row.order_count.toLocaleString()}
                            </td>
                            <td className="py-2.5 pr-4 text-right text-green-600 dark:text-green-400">
                              {formatCurrency(row.revenue)}
                            </td>
                            <td className="py-2.5 pr-4 text-right text-[var(--text-secondary)]">
                              {(row.completed_orders ?? 0).toLocaleString()}
                            </td>
                            <td className="py-2.5 pr-4 text-right text-[var(--text-secondary)]">
                              {(row.cancelled_orders ?? 0).toLocaleString()}
                            </td>
                            <td className="py-2.5 pr-4 text-right text-[var(--text-secondary)]">
                              {formatCurrency(row.refunded_amount)}
                            </td>
                            <td className="py-2.5 text-right text-[var(--text-secondary)]">
                              {formatCurrency(
                                row.order_count > 0 ? Math.round(row.revenue / row.order_count) : 0,
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-sm text-[var(--text-muted)]">No cafeteria sales for this period.</p>
                )}
              </Section>
            </div>
          )}

          {selectedCafeteria && report.performance && (
            <div className="mb-6">
              <Section
                title="Cafeteria Performance"
                subtitle={`${cafeteriaLabel} · ${rangeLabel}`}
              >
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <StatTile label="Total Orders" value={report.performance.total_orders.toLocaleString()} />
                  <StatTile
                    label="Completion Rate"
                    value={formatPct(report.performance.completion_rate)}
                    hint={`${report.performance.completed_orders.toLocaleString()} completed`}
                  />
                  <StatTile
                    label="Cancellation Rate"
                    value={formatPct(report.performance.cancellation_rate)}
                    hint={`${report.performance.cancelled_orders.toLocaleString()} cancelled`}
                  />
                  <StatTile
                    label="Uncollected"
                    value={report.performance.uncollected_orders.toLocaleString()}
                  />
                  <StatTile
                    label="Avg Preparation"
                    value={
                      report.performance.avg_preparation_time_minutes != null
                        ? `${report.performance.avg_preparation_time_minutes} min`
                        : "—"
                    }
                  />
                  <StatTile
                    label="Avg Time to Ready"
                    value={
                      report.performance.avg_time_to_ready_minutes != null
                        ? `${report.performance.avg_time_to_ready_minutes} min`
                        : "—"
                    }
                  />
                  <StatTile
                    label="Avg ETA"
                    value={
                      report.performance.avg_eta_minutes != null
                        ? `${report.performance.avg_eta_minutes} min`
                        : "—"
                    }
                  />
                </div>
              </Section>
            </div>
          )}

          {/* Top items + breakdowns */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
            <Section
              title="Top Menu Items"
              subtitle={`By quantity sold · ${cafeteriaLabel}`}
            >
              {report.popular.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-xs text-[var(--text-muted)] border-b border-[var(--border-default)]">
                        <th className="py-2 pr-3 font-medium">#</th>
                        <th className="py-2 pr-3 font-medium">Item</th>
                        {selectedCafeteria === "" && isAdmin && (
                          <th className="py-2 pr-3 font-medium">Cafeteria</th>
                        )}
                        <th className="py-2 pr-3 font-medium text-right">Qty</th>
                        <th className="py-2 pr-3 font-medium text-right">Revenue</th>
                        <th className="py-2 font-medium text-right">Orders</th>
                      </tr>
                    </thead>
                    <tbody>
                      {report.popular.map((item, idx) => (
                        <tr
                          key={item.menu_item_id ?? item.item_name}
                          className="border-b border-[var(--border-default)] last:border-0"
                        >
                          <td className="py-2 pr-3 text-[var(--text-muted)]">{idx + 1}</td>
                          <td className="py-2 pr-3 font-medium text-[var(--text-primary)]">
                            {item.item_name}
                          </td>
                          {selectedCafeteria === "" && isAdmin && (
                            <td className="py-2 pr-3 text-xs text-[var(--text-muted)]">
                              {item.cafeterias.join(", ")}
                            </td>
                          )}
                          <td className="py-2 pr-3 text-right text-[var(--text-secondary)]">
                            {item.total_quantity.toLocaleString()}
                          </td>
                          <td className="py-2 pr-3 text-right text-green-600 dark:text-green-400">
                            {formatCurrency(item.total_revenue)}
                          </td>
                          <td className="py-2 text-right text-[var(--text-secondary)]">
                            {item.order_count.toLocaleString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-sm text-[var(--text-muted)]">No item sales for this period.</p>
              )}
            </Section>

            <Section
              title="Order Breakdown"
              subtitle={`Status, payment method, and order type · ${rangeLabel}`}
            >
              <StatusBars
                breakdown={report.orderSummary.status_breakdown}
                total={report.orderSummary.total_orders}
              />
              <div className="grid grid-cols-2 gap-4 mt-5">
                <div>
                  <p className="text-xs font-medium text-[var(--text-muted)] uppercase mb-2">
                    Payment Method (order counts)
                  </p>
                  <div className="space-y-1.5 text-sm text-[var(--text-secondary)]">
                    <div className="flex justify-between">
                      <span>Cash</span>
                      <span className="font-medium">{report.orderSummary.payment_breakdown.cash.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Online</span>
                      <span className="font-medium">{report.orderSummary.payment_breakdown.online.toLocaleString()}</span>
                    </div>
                  </div>
                </div>
                <div>
                  <p className="text-xs font-medium text-[var(--text-muted)] uppercase mb-2">Order Type</p>
                  <div className="space-y-1.5 text-sm text-[var(--text-secondary)]">
                    <div className="flex justify-between">
                      <span>Immediate</span>
                      <span className="font-medium">{report.orderSummary.type_breakdown.immediate.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Scheduled</span>
                      <span className="font-medium">{report.orderSummary.type_breakdown.scheduled.toLocaleString()}</span>
                    </div>
                  </div>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4 mt-4">
                <StatTile
                  label="Completion Rate"
                  value={formatPct(report.orderSummary.completion_rate)}
                />
                <StatTile
                  label="Cancellation Rate"
                  value={formatPct(report.orderSummary.cancellation_rate)}
                />
              </div>
            </Section>
          </div>

          {/* Cancellation reasons + hourly volume */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
            <Section
              title="Cancellation Reasons"
              subtitle="Recorded reasons on cancelled orders · backend order events"
            >
              {Object.keys(report.cancellation.cancellation_reasons).length > 0 ? (
                <div className="space-y-1.5">
                  {Object.entries(report.cancellation.cancellation_reasons).map(([reason, count]) => (
                    <div
                      key={reason}
                      className="flex justify-between text-sm text-[var(--text-secondary)] border-b border-[var(--border-default)] pb-1.5 last:border-0"
                    >
                      <span className="capitalize">{reason.replace(/_/g, " ")}</span>
                      <span className="font-medium">{Number(count).toLocaleString()}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-[var(--text-muted)]">No cancellations recorded.</p>
              )}
            </Section>
            <Section
              title="Hourly Order Volume"
              subtitle="Orders by hour of day (created_at) · respects filters"
            >
              {report.volume.hourly.some((h) => h.order_count > 0) ? (
                <HourlyStrip hours={report.volume.hourly} />
              ) : (
                <p className="text-sm text-[var(--text-muted)]">No orders in this period.</p>
              )}
            </Section>
          </div>

          {/* Daily detail table */}
          <div className="mb-6">
            <Section title="Daily Detail" subtitle={`Orders and revenue per day · ${rangeLabel}`}>
              {dailyTable.length > 0 ? (
                <div className="overflow-x-auto max-h-96 overflow-y-auto">
                  <table className="w-full text-sm">
                    <thead className="sticky top-0 bg-[var(--bg-primary)]">
                      <tr className="text-left text-xs text-[var(--text-muted)] border-b border-[var(--border-default)]">
                        <th className="py-2 pr-4 font-medium">Date</th>
                        <th className="py-2 pr-4 font-medium text-right">Orders</th>
                        <th className="py-2 pr-4 font-medium text-right">Completed</th>
                        <th className="py-2 pr-4 font-medium text-right">Cancelled</th>
                        <th className="py-2 font-medium text-right">Revenue</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dailyTable.map((row) => (
                        <tr
                          key={row.date}
                          className="border-b border-[var(--border-default)] last:border-0"
                        >
                          <td className="py-2 pr-4 text-[var(--text-secondary)]">
                            {new Date(`${row.date}T00:00:00`).toLocaleDateString("en-US", {
                              month: "short",
                              day: "numeric",
                              year: "numeric",
                            })}
                          </td>
                          <td className="py-2 pr-4 text-right text-[var(--text-secondary)]">
                            {row.order_count.toLocaleString()}
                          </td>
                          <td className="py-2 pr-4 text-right text-green-600 dark:text-green-400">
                            {row.completed.toLocaleString()}
                          </td>
                          <td className="py-2 pr-4 text-right text-red-600 dark:text-red-400">
                            {row.cancelled.toLocaleString()}
                          </td>
                          <td className="py-2 text-right text-[var(--text-secondary)]">
                            {formatCurrency(row.revenue)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-sm text-[var(--text-muted)]">
                  No daily activity for this period.
                </p>
              )}
            </Section>
          </div>

          {/* Phase 58 (Workstream C) — inventory reports + peak hours.
              These four endpoints are cafeteria-scoped on the backend, so
              they render only for a selected cafeteria. A load failure shows
              its own error state and never masquerades as "no data". */}
          {selectedCafeteria && inventoryReportsError && (
            <div className="mb-6">
              <LoadErrorState
                error={inventoryReportsError}
                subject="inventory/peak-hour reports"
                onRetry={() => setReloadKey((k) => k + 1)}
              />
            </div>
          )}

          {selectedCafeteria && report.inventory && (
            <>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
                <Section
                  title="Inventory Stock Levels"
                  subtitle={`Current stock snapshot · ${cafeteriaLabel}`}
                >
                  <div className="grid grid-cols-3 gap-3 mb-4">
                    <StatTile
                      label="Inventory Items"
                      value={report.inventory.stockLevels.total_items.toLocaleString()}
                    />
                    <StatTile
                      label="Low Stock"
                      value={report.inventory.stockLevels.low_stock_count.toLocaleString()}
                    />
                    <StatTile
                      label="Out of Stock"
                      value={report.inventory.stockLevels.out_of_stock_count.toLocaleString()}
                    />
                  </div>
                  {report.inventory.stockLevels.items.length > 0 ? (
                    <div className="overflow-x-auto max-h-80 overflow-y-auto">
                      <table className="w-full text-sm">
                        <thead className="sticky top-0 bg-[var(--bg-primary)]">
                          <tr className="text-left text-xs text-[var(--text-muted)] border-b border-[var(--border-default)]">
                            <th className="py-2 pr-3 font-medium">Item</th>
                            <th className="py-2 pr-3 font-medium text-right">Qty</th>
                            <th className="py-2 pr-3 font-medium text-right">Threshold</th>
                            <th className="py-2 font-medium text-right">Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {report.inventory.stockLevels.items.map((row) => (
                            <tr
                              key={row.inventory_item_id}
                              className="border-b border-[var(--border-default)] last:border-0"
                            >
                              <td className="py-2 pr-3 font-medium text-[var(--text-primary)]">
                                {row.menu_item_name}
                              </td>
                              <td className="py-2 pr-3 text-right text-[var(--text-secondary)]">
                                {row.quantity.toLocaleString()} {row.unit}
                              </td>
                              <td className="py-2 pr-3 text-right text-[var(--text-secondary)]">
                                {row.low_threshold.toLocaleString()} {row.unit}
                              </td>
                              <td className="py-2 text-right">
                                {row.is_out_of_stock ? (
                                  <span className="px-2 py-0.5 rounded-full text-[11px] font-medium bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">
                                    Out of stock
                                  </span>
                                ) : row.is_low_stock ? (
                                  <span className="px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
                                    Low stock
                                  </span>
                                ) : (
                                  <span className="px-2 py-0.5 rounded-full text-[11px] font-medium bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">
                                    In stock
                                  </span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="text-sm text-[var(--text-muted)]">
                      No inventory items recorded for this cafeteria.
                    </p>
                  )}
                </Section>

                <Section
                  title="Low Stock"
                  subtitle={`Items at or below threshold · ${cafeteriaLabel}`}
                >
                  {report.inventory.lowStock.items.length > 0 ? (
                    <div className="overflow-x-auto max-h-80 overflow-y-auto">
                      <table className="w-full text-sm">
                        <thead className="sticky top-0 bg-[var(--bg-primary)]">
                          <tr className="text-left text-xs text-[var(--text-muted)] border-b border-[var(--border-default)]">
                            <th className="py-2 pr-3 font-medium">Item</th>
                            <th className="py-2 pr-3 font-medium text-right">Qty</th>
                            <th className="py-2 pr-3 font-medium text-right">Threshold</th>
                            <th className="py-2 font-medium text-right">Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {report.inventory.lowStock.items.map((row) => (
                            <tr
                              key={row.inventory_item_id}
                              className="border-b border-[var(--border-default)] last:border-0"
                            >
                              <td className="py-2 pr-3 font-medium text-[var(--text-primary)]">
                                {row.menu_item_name}
                              </td>
                              <td className="py-2 pr-3 text-right text-[var(--text-secondary)]">
                                {row.quantity.toLocaleString()} {row.unit}
                              </td>
                              <td className="py-2 pr-3 text-right text-[var(--text-secondary)]">
                                {row.low_threshold.toLocaleString()} {row.unit}
                              </td>
                              <td className="py-2 text-right">
                                {row.stock_status === "out_of_stock" ? (
                                  <span className="px-2 py-0.5 rounded-full text-[11px] font-medium bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">
                                    Out of stock
                                  </span>
                                ) : (
                                  <span className="px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
                                    Low stock
                                  </span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="text-sm text-[var(--text-muted)]">
                      Every inventory item is above its low-stock threshold.
                    </p>
                  )}
                </Section>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
                <Section
                  title="Inventory Turnover"
                  subtitle={`Restock vs usage adjustments · ${rangeLabel}`}
                >
                  <div className="grid grid-cols-3 gap-3 mb-4">
                    <StatTile
                      label="Adjustments"
                      value={report.inventory.turnover.total_adjustments.toLocaleString()}
                    />
                    <StatTile
                      label="Restock (units)"
                      value={report.inventory.turnover.total_restock.toLocaleString()}
                    />
                    <StatTile
                      label="Usage (units)"
                      value={report.inventory.turnover.total_usage.toLocaleString()}
                    />
                  </div>
                  {report.inventory.turnover.adjustments.length > 0 ? (
                    <div className="overflow-x-auto max-h-72 overflow-y-auto">
                      <table className="w-full text-sm">
                        <thead className="sticky top-0 bg-[var(--bg-primary)]">
                          <tr className="text-left text-xs text-[var(--text-muted)] border-b border-[var(--border-default)]">
                            <th className="py-2 pr-3 font-medium">Item</th>
                            <th className="py-2 pr-3 font-medium text-right">Δ Qty</th>
                            <th className="py-2 pr-3 font-medium">Reason</th>
                            <th className="py-2 font-medium text-right">Adjusted</th>
                          </tr>
                        </thead>
                        <tbody>
                          {report.inventory.turnover.adjustments.map((row) => (
                            <tr
                              key={row.id}
                              className="border-b border-[var(--border-default)] last:border-0"
                            >
                              <td className="py-2 pr-3 font-medium text-[var(--text-primary)]">
                                {row.menu_item_name}
                              </td>
                              <td
                                className={`py-2 pr-3 text-right font-medium ${
                                  row.adjustment_quantity >= 0
                                    ? "text-green-600 dark:text-green-400"
                                    : "text-red-600 dark:text-red-400"
                                }`}
                              >
                                {row.adjustment_quantity >= 0
                                  ? `+${row.adjustment_quantity}`
                                  : row.adjustment_quantity}
                              </td>
                              <td className="py-2 pr-3 text-xs text-[var(--text-secondary)] capitalize">
                                {row.reason ? row.reason.replace(/_/g, " ") : "—"}
                              </td>
                              <td className="py-2 text-right text-xs text-[var(--text-muted)]">
                                {new Date(row.adjusted_at).toLocaleString("en-US", {
                                  month: "short",
                                  day: "numeric",
                                  hour: "2-digit",
                                  minute: "2-digit",
                                })}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="text-sm text-[var(--text-muted)]">
                      No inventory adjustments in this period.
                    </p>
                  )}
                  <p className="text-[11px] text-[var(--text-muted)] mt-3">
                    Restock = sum of positive adjustments · Usage = absolute sum of negative
                    adjustments · backend inventory adjustment records.
                  </p>
                </Section>

                <Section
                  title="Peak Hours"
                  subtitle={`Orders by hour of day (created_at) · ${rangeLabel}`}
                >
                  <p className="text-[11px] text-[var(--text-muted)] mb-3">
                    Cafeteria timezone: {report.inventory.peakHours.timezone}
                  </p>
                  {report.inventory.peakHours.hours.some((h) => h.order_count > 0) ? (
                    <HourlyStrip hours={report.inventory.peakHours.hours} />
                  ) : (
                    <p className="text-sm text-[var(--text-muted)]">No orders in this period.</p>
                  )}
                </Section>
              </div>
            </>
          )}

          {!selectedCafeteria && (
            <div className="mb-6">
              <Section
                title="Inventory & Peak-Hour Reports"
                subtitle="Cafeteria-scoped backend reports"
              >
                <p className="text-sm text-[var(--text-muted)]">
                  Stock levels, low stock, inventory turnover, and peak-hour reports are served
                  per cafeteria by the backend. Select a specific cafeteria above to view them.
                </p>
              </Section>
            </div>
          )}

          {/* Metric definitions — backend terminology, no invented definitions */}
          <div className="text-[11px] text-[var(--text-muted)] space-y-1 mb-4">
            <p>
              Revenue = succeeded payments on orders in the selected period; net revenue is after
              succeeded refunds. Total Orders counts all orders; Avg Order Value = revenue ÷ paid
              orders. Online/Cash Paid are succeeded payment volumes by order payment method.
              Payment-method breakdown shows order counts, not volumes. All amounts in PKR.
            </p>
            {isManager && !isAdmin && (
              <p>Manager reports are limited to your assigned cafeteria.</p>
            )}
          </div>
        </>
      )}
    </div>
  );
}
