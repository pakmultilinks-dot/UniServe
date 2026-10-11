/**
 * UniServe — University email classification & validation (Phase 47).
 *
 * Mirrors the backend's configured student/faculty email patterns
 * (`apps/api/app/core/config.py` → university_email_patterns), which are
 * enforced server-side at AUTH REGISTER time via
 * `app/core/university.py: classify_university_email`.
 *
 * The admin `POST /users/` endpoint intentionally uses plain EmailStr
 * (administrators may need to create accounts that self-registration would
 * not allow). The frontend uses these SAME configured patterns as blocking,
 * helpful inline validation so admins catch typos before submitting — the
 * backend remains authoritative for format, duplicates, and role rules.
 */

export type UniversityEmailGroup = "student" | "faculty";

/** Exact regex sources mirrored from backend config (Python `re` → JS RegExp). */
export const UNIVERSITY_EMAIL_PATTERNS: Record<UniversityEmailGroup, RegExp[]> = {
  student: [/^fa\d{2}-.+@lgu\.edu\.pk$/i, /.+@student\.lgu\.edu\.pk$/i],
  faculty: [/^[a-z].*@lgu\.edu\.pk$/i, /.+@faculty\.lgu\.edu\.pk$/i],
};

export function classifyUniversityEmail(email: string): UniversityEmailGroup | null {
  const normalized = email.trim().toLowerCase();
  if (!normalized) return null;
  if (UNIVERSITY_EMAIL_PATTERNS.student.some((p) => p.test(normalized))) return "student";
  if (UNIVERSITY_EMAIL_PATTERNS.faculty.some((p) => p.test(normalized))) return "faculty";
  return null;
}

/**
 * Role → expected email group, mirroring the backend create_user category map
 * (staff/manager/admin accounts are FACULTY-category, so they follow the
 * faculty email pattern).
 */
function expectedGroupForRole(role: string): UniversityEmailGroup | null {
  switch (role) {
    case "student":
      return "student";
    case "faculty":
    case "cafeteria_staff":
    case "cafeteria_manager":
    case "university_admin":
      return "faculty";
    default:
      return null;
  }
}

/**
 * Returns a human-readable error when the email does not match the patterns
 * configured for the given role, or null when acceptable.
 *
 * Note: the backend does NOT enforce these patterns on admin-created users —
 * this is a helpful guardrail only.
 */
export function validateUniversityEmailForRole(
  email: string,
  role: string,
): string | null {
  const expected = expectedGroupForRole(role);
  if (!expected) return null; // Unknown role — backend enum validation will reject it.
  const normalized = email.trim().toLowerCase();
  if (!normalized) return null; // Empty handled by required-field validation.
  if (classifyUniversityEmail(normalized) === expected) return null;
  if (expected === "student") {
    return "Student emails must look like fa22-bse-001@lgu.edu.pk or name@student.lgu.edu.pk.";
  }
  return "Faculty/staff emails must look like name@lgu.edu.pk or name@faculty.lgu.edu.pk.";
}
