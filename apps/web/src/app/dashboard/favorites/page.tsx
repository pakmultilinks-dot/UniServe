"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { PageHeader } from "@/components/ui/PageHeader";
import { EmptyState } from "@/components/ui/EmptyState";
import { StatusBadge } from "@/components/ui/StatusBadge";

export default function FavoritesPage() {
  const { user } = useAuth();
  const [favorites, setFavorites] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const loadFavorites = useCallback(async () => {
    setLoading(true);
    try {
      const token = typeof window !== "undefined" ? sessionStorage.getItem("uniserve_refresh_token") : null;
      // Use the same api base
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/favorites`, {
        headers: { Authorization: `Bearer ${sessionStorage.getItem("uniserve_token") ?? ""}` },
      });
      if (res.ok) {
        const data = await res.json();
        setFavorites(Array.isArray(data) ? data : data.items ?? []);
      } else {
        setFavorites([]);
      }
    } catch {
      setFavorites([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadFavorites(); }, [loadFavorites]);

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="My Favorites"
        description="Your saved menu items"
      />

      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-40 bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl skeleton" />
          ))}
        </div>
      ) : favorites.length === 0 ? (
        <EmptyState
          title="No favorites yet"
          description="Items you save from the menu will appear here."
          icon={
            <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 8.25c0-2.485-2.099-4.5-4.688-4.5-1.935 0-3.597 1.126-4.312 2.733-.715-1.607-2.377-2.733-4.313-2.733C5.1 3.75 3 5.765 3 8.25c0 7.22 9 12 9 12s9-4.78 9-12z" />
            </svg>
          }
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {favorites.map((fav) => {
            const item = fav.menu_item ?? fav;
            return (
              <div key={fav.id} className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl p-4 shadow-card hover:shadow-lg transition-shadow">
                <h3 className="font-semibold text-[var(--text-primary)]">{item.name ?? "Unknown Item"}</h3>
                {item.description && (
                  <p className="text-xs text-[var(--text-muted)] mt-1 line-clamp-2">{item.description}</p>
                )}
                <div className="flex items-center justify-between mt-3">
                  <span className="text-sm font-bold text-green-600 dark:text-green-400">
                    Rs. {item.price ?? 0}
                  </span>
                  {item.category && (
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-[var(--bg-secondary)] text-[var(--text-muted)] capitalize">
                      {item.category}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}