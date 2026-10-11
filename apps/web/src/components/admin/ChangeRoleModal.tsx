"use client";

import React, { useState } from "react";
import type { Cafeteria, User, UserRole } from "@uniserve/shared-types";
import { changeUserRole, getApiErrorInfo } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/Toast";
import { ModalShell } from "./ModalShell";
import { RoleBadge, roleLabel } from "./RoleBadge";

interface ChangeRoleModalProps {
  member: User;
  /**
   * "role" — change the member's role (staff/manager reveal a required
   * cafeteria picker — the Phase 45 P0 bug fix).
   * "cafeteria" — reassign a staff/manager to a different cafeteria via the
   * same PUT /users/{id}/role endpoint with the current role.
   */
  mode: "role" | "cafeteria";
  cafeterias: Cafeteria[];
  onClose: () => void;
  onUpdated: () => void;
}

const ALL_ROLES: UserRole[] = ["student", "faculty", "cafeteria_staff", "cafeteria_manager", "university_admin"];

/**
 * Phase 47 — role change & cafeteria reassignment dialog.
 * Backend PUT /users/{id}/role requires cafeteria_id for staff/manager; this
 * dialog always sends it for those roles and confirms the change explicitly.
 */
export function ChangeRoleModal({
  member,
  mode,
  cafeterias,
  onClose,
  onUpdated,
}: ChangeRoleModalProps) {
  const { toast } = useToast();
  const [newRole, setNewRole] = useState<UserRole>(
    mode === "cafeteria" ? member.role : member.role,
  );
  const [newCafeteriaId, setNewCafeteriaId] = useState<string>(
    mode === "cafeteria" ? (member.cafeteria_id ?? "") : "",
  );
  const [submitting, setSubmitting] = useState(false);

  const roleNeedsCafeteria = newRole === "cafeteria_staff" || newRole === "cafeteria_manager";
  const isCafeteriaMode = mode === "cafeteria";

  // In cafeteria mode the target role never changes; only the assignment does.
  const effectiveRole = isCafeteriaMode ? member.role : newRole;
  const effectiveNeedsCafeteria =
    effectiveRole === "cafeteria_staff" || effectiveRole === "cafeteria_manager";
  const canSubmit =
    !effectiveNeedsCafeteria ||
    (newCafeteriaId.length > 0 && newCafeteriaId !== member.cafeteria_id) ||
    (!isCafeteriaMode && newCafeteriaId.length > 0);

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    try {
      // One coherent workflow: PUT /users/{id}/role with the (possibly
      // unchanged) role + the cafeteria_id. Backend upserts the assignment.
      await changeUserRole(
        member.id,
        effectiveRole,
        effectiveNeedsCafeteria ? newCafeteriaId : undefined,
      );
      toast(
        isCafeteriaMode ? "Cafeteria assignment updated." : "Role updated successfully.",
        "success",
      );
      onUpdated();
      // Phase 47 E2E: the dialog is a one-shot confirm flow — close it after a
      // successful change so the operator returns to the refreshed list.
      onClose();
    } catch (err) {
      const info = getApiErrorInfo(err);
      toast(info.message, "error");
    } finally {
      setSubmitting(false);
    }
  };

  if (isCafeteriaMode) {
    return (
      <ModalShell onClose={onClose}>
        <h3 className="text-base font-semibold text-[var(--text-primary)] mb-2">
          Change Cafeteria
        </h3>
        <p className="text-sm text-[var(--text-secondary)] mb-4">
          {member.first_name} {member.last_name} currently works at{" "}
          <span className="font-medium text-[var(--text-primary)]">
            {member.cafeteria_name ?? "an unassigned cafeteria"}
          </span>
          .
        </p>

        <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1.5">
          New cafeteria
        </label>
        <select
          value={newCafeteriaId}
          onChange={(e) => setNewCafeteriaId(e.target.value)}
          disabled={submitting}
          className="w-full px-3 py-2.5 text-sm rounded-lg border border-[var(--border-default)] bg-[var(--bg-primary)] text-[var(--text-primary)] focus:border-brand-500 focus:outline-none disabled:opacity-50"
        >
          <option value="">Select a cafeteria…</option>
          {cafeterias.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>

        <div className="flex justify-end gap-2 mt-6">
          <Button size="sm" variant="ghost" onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button
            size="sm"
            onClick={handleSubmit}
            loading={submitting}
            disabled={!canSubmit}
          >
            Save Assignment
          </Button>
        </div>
      </ModalShell>
    );
  }

  return (
    <ModalShell onClose={onClose}>
      <h3 className="text-base font-semibold text-[var(--text-primary)] mb-2">Change Role</h3>
      <p className="text-sm text-[var(--text-secondary)] mb-4">
        <span className="font-medium text-[var(--text-primary)]">
          {member.first_name} {member.last_name}
        </span>{" "}
        is currently a <RoleBadge role={member.role} />.
      </p>

      <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1.5">
        New role
      </label>
      <select
        value={newRole}
        onChange={(e) => setNewRole(e.target.value as UserRole)}
        disabled={submitting}
        className="w-full px-3 py-2.5 text-sm rounded-lg border border-[var(--border-default)] bg-[var(--bg-primary)] text-[var(--text-primary)] focus:border-brand-500 focus:outline-none disabled:opacity-50"
      >
        {ALL_ROLES.map((r) => (
          <option key={r} value={r}>{roleLabel(r)}</option>
        ))}
      </select>

      {roleNeedsCafeteria && (
        <div className="mt-4">
          <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1.5">
            Cafeteria
          </label>
          <select
            value={newCafeteriaId}
            onChange={(e) => setNewCafeteriaId(e.target.value)}
            disabled={submitting}
            className="w-full px-3 py-2.5 text-sm rounded-lg border border-[var(--border-default)] bg-[var(--bg-primary)] text-[var(--text-primary)] focus:border-brand-500 focus:outline-none disabled:opacity-50"
          >
            <option value="">Select a cafeteria…</option>
            {cafeterias.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
          <p className="mt-1.5 text-xs text-[var(--text-muted)]">
            Staff and Manager accounts must be assigned to a cafeteria.
          </p>
        </div>
      )}

      <p className="mt-4 text-sm text-[var(--text-secondary)]">
        Change {member.first_name} {member.last_name} to{" "}
        <span className="font-medium text-[var(--text-primary)]">{roleLabel(newRole)}</span>
        {roleNeedsCafeteria && newCafeteriaId
          ? ` at ${cafeterias.find((c) => c.id === newCafeteriaId)?.name ?? "the selected cafeteria"}?`
          : "?"}
      </p>

      <div className="flex justify-end gap-2 mt-6">
        <Button size="sm" variant="ghost" onClick={onClose} disabled={submitting}>
          Cancel
        </Button>
        <Button size="sm" onClick={handleSubmit} loading={submitting} disabled={!canSubmit}>
          Confirm Change
        </Button>
      </div>
    </ModalShell>
  );
}
