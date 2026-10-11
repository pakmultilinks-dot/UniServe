"use client";

import React, { useState } from "react";
import type { Cafeteria, UserRole } from "@uniserve/shared-types";
import { createUser, getApiErrorInfo } from "@/lib/api";
import { validateUniversityEmailForRole } from "@/lib/universityEmail";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { useToast } from "@/components/ui/Toast";
import { ModalShell } from "./ModalShell";
import { roleLabel } from "./RoleBadge";

interface AddMemberModalProps {
  cafeterias: Cafeteria[];
  /** Role pre-selected in the form (e.g. "cafeteria_staff" from Staff page). */
  preselectedRole?: UserRole;
  onClose: () => void;
  /** Called after a successful create so the parent can refresh its list. */
  onCreated: () => void;
}

interface FormErrors {
  first_name?: string;
  last_name?: string;
  university_id?: string;
  university_email?: string;
  role?: string;
  cafeteria_id?: string;
}

const ROLE_GROUPS: { group: string; roles: { value: UserRole; label: string }[] }[] = [
  {
    group: "University members",
    roles: [
      { value: "student", label: "Student" },
      { value: "faculty", label: "Faculty" },
    ],
  },
  {
    group: "Operational",
    roles: [
      { value: "cafeteria_staff", label: "Staff" },
      { value: "cafeteria_manager", label: "Manager" },
    ],
  },
  {
    group: "Administration",
    roles: [{ value: "university_admin", label: "University Admin" }],
  },
];

const ALL_ROLES: UserRole[] = ["student", "faculty", "cafeteria_staff", "cafeteria_manager", "university_admin"];

function validateForm(
  form: { first_name: string; last_name: string; university_id: string; university_email: string; role: UserRole; cafeteria_id: string },
): FormErrors {
  const errors: FormErrors = {};
  if (!form.first_name.trim()) errors.first_name = "First name is required.";
  else if (form.first_name.trim().length > 255) errors.first_name = "First name must be 255 characters or fewer.";
  if (!form.last_name.trim()) errors.last_name = "Last name is required.";
  else if (form.last_name.trim().length > 255) errors.last_name = "Last name must be 255 characters or fewer.";
  if (!form.university_id.trim()) errors.university_id = "University ID is required.";
  else if (form.university_id.trim().length < 3) errors.university_id = "University ID must be at least 3 characters.";
  else if (form.university_id.trim().length > 50) errors.university_id = "University ID must be 50 characters or fewer.";
  if (!form.university_email.trim()) {
    errors.university_email = "University email is required.";
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.university_email.trim())) {
    errors.university_email = "Enter a valid email address.";
  } else {
    // Helpful guardrail mirroring the backend's configured patterns — the
    // backend remains authoritative (admin creation allows plain EmailStr).
    const emailError = validateUniversityEmailForRole(form.university_email, form.role);
    if (emailError) errors.university_email = emailError;
  }
  if (!ALL_ROLES.includes(form.role)) errors.role = "Select a valid role.";
  if (
    (form.role === "cafeteria_staff" || form.role === "cafeteria_manager") &&
    !form.cafeteria_id
  ) {
    errors.cafeteria_id = "Cafeteria is required for Staff accounts.";
  }
  return errors;
}

/**
 * Phase 47 — Admin "Add Member" dialog.
 * Calls the real POST /users/ endpoint. On success shows the temporary
 * password exactly once (with a copy button) — it is never re-fetchable.
 */
export function AddMemberModal({
  cafeterias,
  preselectedRole = "student",
  onClose,
  onCreated,
}: AddMemberModalProps) {
  const { toast } = useToast();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [universityId, setUniversityId] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<UserRole>(preselectedRole);
  const [cafeteriaId, setCafeteriaId] = useState("");
  const [errors, setErrors] = useState<FormErrors>({});
  const [submitting, setSubmitting] = useState(false);
  const [createdPassword, setCreatedPassword] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const roleNeedsCafeteria = role === "cafeteria_staff" || role === "cafeteria_manager";

  const handleSubmit = async () => {
    const form = {
      first_name: firstName,
      last_name: lastName,
      university_id: universityId,
      university_email: email,
      role,
      cafeteria_id: cafeteriaId,
    };
    const validationErrors = validateForm(form);
    setErrors(validationErrors);
    if (Object.keys(validationErrors).length > 0) return;

    setSubmitting(true);
    try {
      const response = await createUser({
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        university_id: form.university_id.trim(),
        university_email: form.university_email.trim(),
        role: form.role,
        cafeteria_id: roleNeedsCafeteria ? form.cafeteria_id : undefined,
      });
      setCreatedPassword(response.temporary_password);
      toast("Member created.", "success");
      onCreated();
    } catch (err) {
      const info = getApiErrorInfo(err);
      toast(info.message, "error");
    } finally {
      setSubmitting(false);
    }
  };

  const handleCopy = async () => {
    if (!createdPassword) return;
    try {
      await navigator.clipboard.writeText(createdPassword);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast("Could not copy to clipboard — select the password and copy manually.", "error");
    }
  };

  // ─── Success panel: one-time password ───
  if (createdPassword) {
    return (
      <ModalShell onClose={onClose}>
        <h3 className="text-base font-semibold text-[var(--text-primary)] mb-2">Member Created</h3>
        <p className="text-sm text-[var(--text-secondary)] mb-4">
          The account is active and the email is pre-verified. Share this temporary
          password securely — it is shown only once and cannot be retrieved again.
        </p>
        <div className="flex items-center gap-2 mb-4">
          <code className="flex-1 px-3 py-2 text-sm font-mono bg-[var(--bg-secondary)] border border-[var(--border-default)] rounded-lg text-[var(--text-primary)] select-all">
            {createdPassword}
          </code>
          <Button size="sm" variant="secondary" onClick={handleCopy}>
            {copied ? "Copied" : "Copy"}
          </Button>
        </div>
        <div className="flex justify-end">
          <Button size="sm" onClick={onClose}>Done</Button>
        </div>
      </ModalShell>
    );
  }

  return (
    <ModalShell onClose={onClose} maxWidth="max-w-md">
      <h3 className="text-base font-semibold text-[var(--text-primary)] mb-4">Add Member</h3>

      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <Input
            label="First name"
            value={firstName}
            onChange={(e) => setFirstName(e.target.value)}
            error={errors.first_name}
            placeholder="Ali"
            disabled={submitting}
          />
          <Input
            label="Last name"
            value={lastName}
            onChange={(e) => setLastName(e.target.value)}
            error={errors.last_name}
            placeholder="Raza"
            disabled={submitting}
          />
        </div>

        <Input
          label="University ID"
          value={universityId}
          onChange={(e) => setUniversityId(e.target.value)}
          error={errors.university_id}
          placeholder="FA22-BSE-001"
          disabled={submitting}
        />

        <Input
          label="University email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={errors.university_email}
          placeholder="ali.raza@lgu.edu.pk"
          disabled={submitting}
        />

        <div className="w-full">
          <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1.5">
            Role
          </label>
          <select
            value={role}
            onChange={(e) => setRole(e.target.value as UserRole)}
            disabled={submitting}
            className="w-full px-3 py-2.5 text-sm rounded-lg border border-[var(--border-default)] bg-[var(--bg-primary)] text-[var(--text-primary)] focus:border-brand-500 focus:outline-none disabled:opacity-50"
          >
            {ROLE_GROUPS.map((group) => (
              <optgroup key={group.group} label={group.group}>
                {group.roles.map((r) => (
                  <option key={r.value} value={r.value}>{r.label}</option>
                ))}
              </optgroup>
            ))}
          </select>
          {errors.role && <p className="mt-1.5 text-xs text-red-600" role="alert">{errors.role}</p>}
        </div>

        {roleNeedsCafeteria && (
          <div className="w-full">
            <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1.5">
              Cafeteria
            </label>
            <select
              value={cafeteriaId}
              onChange={(e) => setCafeteriaId(e.target.value)}
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
            {errors.cafeteria_id && (
              <p className="mt-1.5 text-xs text-red-600" role="alert">{errors.cafeteria_id}</p>
            )}
          </div>
        )}
      </div>

      <div className="flex justify-end gap-2 mt-6">
        <Button size="sm" variant="ghost" onClick={onClose} disabled={submitting}>
          Cancel
        </Button>
        <Button size="sm" onClick={handleSubmit} loading={submitting}>
          Create {roleLabel(role)}
        </Button>
      </div>
    </ModalShell>
  );
}
