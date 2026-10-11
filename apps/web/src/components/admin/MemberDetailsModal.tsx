"use client";

import React, { useCallback, useEffect, useState } from "react";
import type { User } from "@uniserve/shared-types";
import { getUserDetail, getApiErrorInfo } from "@/lib/api";
import type { ApiErrorInfo } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { LoadErrorState } from "@/components/ui/LoadErrorState";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ModalShell } from "./ModalShell";
import { RoleBadge } from "./RoleBadge";

interface MemberDetailsModalProps {
  userId: string;
  onClose: () => void;
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

/**
 * Phase 47 — read-only member detail dialog.
 * Fetches the real GET /users/{id} (admin endpoint, includes cafeteria
 * assignment). Load failures render LoadErrorState with retry — never a
 * fake "empty" panel.
 */
export function MemberDetailsModal({ userId, onClose }: MemberDetailsModalProps) {
  const [member, setMember] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiErrorInfo | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getUserDetail(userId);
      setMember(data);
      setError(null);
    } catch (err) {
      setError(getApiErrorInfo(err));
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <ModalShell onClose={onClose} maxWidth="max-w-md">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-base font-semibold text-[var(--text-primary)]">Member Details</h3>
        <Button size="sm" variant="ghost" onClick={onClose}>Close</Button>
      </div>

      {loading ? (
        <div className="space-y-3 py-2">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-5 bg-[var(--bg-secondary)] rounded skeleton" />
          ))}
        </div>
      ) : error ? (
        <LoadErrorState
          error={error}
          subject="member details"
          onRetry={load}
          compact
        />
      ) : member ? (
        <dl className="space-y-3 text-sm">
          <div className="flex justify-between gap-4">
            <dt className="text-[var(--text-muted)]">Name</dt>
            <dd className="font-medium text-[var(--text-primary)] text-right">
              {member.first_name} {member.last_name}
            </dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-[var(--text-muted)]">Email</dt>
            <dd className="text-[var(--text-primary)] text-right break-all">
              {member.university_email}
            </dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-[var(--text-muted)]">University ID</dt>
            <dd className="font-mono text-xs text-[var(--text-primary)]">{member.university_id}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-[var(--text-muted)]">Role</dt>
            <dd><RoleBadge role={member.role} /></dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-[var(--text-muted)]">Status</dt>
            <dd><StatusBadge status={member.status} /></dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-[var(--text-muted)]">Email verified</dt>
            <dd className="text-[var(--text-primary)]">
              {member.email_verified ? "Yes" : "No"}
            </dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-[var(--text-muted)]">Cafeteria</dt>
            <dd className="text-[var(--text-primary)] text-right">
              {member.cafeteria_name ?? "Not assigned"}
            </dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-[var(--text-muted)]">Joined</dt>
            <dd className="text-[var(--text-primary)]">{formatDate(member.created_at)}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-[var(--text-muted)]">Last updated</dt>
            <dd className="text-[var(--text-primary)]">{formatDate(member.updated_at)}</dd>
          </div>
        </dl>
      ) : null}
    </ModalShell>
  );
}
