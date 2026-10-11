/**
 * Phase 60 (Workstream A) — Sidebar role-aware navigation tests.
 *
 * Asserts the rendered navigation per authenticated role (behaviour of
 * `getNavForRole` as exercised through the Sidebar component), the active
 * link indicator, and that non-dashboard roles see no nav at all.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { AnchorHTMLAttributes } from "react";

let currentPath = "/dashboard";

vi.mock("next/navigation", () => ({
  usePathname: () => currentPath,
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...rest
  }: AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

vi.mock("@/components/LguBrand", () => ({
  LguBrand: () => <div data-testid="brand" />,
  LguSeal: () => <div data-testid="seal" />,
}));

vi.mock("@/components/ui/Avatar", () => ({
  Avatar: () => <div data-testid="avatar" />,
}));

const useAuthMock = vi.fn();
vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => useAuthMock(),
}));

import { Sidebar } from "@/components/Sidebar";

function authAs(role: string | null) {
  useAuthMock.mockReturnValue({
    user: role
      ? {
          id: "u1",
          role,
          first_name: "Test",
          last_name: "User",
          university_email: "test.user@lgu.edu.pk",
        }
      : null,
    logout: vi.fn().mockResolvedValue(undefined),
  });
}

function navLabels(): string[] {
  // Desktop + mobile both render a <nav>; labels come from <span> inside <a>.
  return Array.from(document.querySelectorAll("nav a")).map(
    (a) => a.textContent ?? "",
  );
}

beforeEach(() => {
  currentPath = "/dashboard";
});

describe("Sidebar — role-aware navigation", () => {
  it("renders the full admin console for university_admin", () => {
    authAs("university_admin");
    render(<Sidebar />);
    const labels = navLabels();
    for (const expected of [
      "Home",
      "Cafeterias",
      "Orders",
      "Notifications",
      "Profile",
      "Staff",
      "Users",
      "Audit Log",
      "Refunds",
      "Settings",
    ]) {
      expect(labels).toContain(expected);
    }
    expect(labels).not.toContain("Daily Menu");
  });

  it("renders the manager console with the 'Daily Menu' label", () => {
    authAs("cafeteria_manager");
    render(<Sidebar />);
    const labels = navLabels();
    expect(labels).toContain("Daily Menu");
    expect(labels).toContain("Reports");
    expect(labels).toContain("Inventory");
    expect(labels).not.toContain("Users");
    expect(labels).not.toContain("Audit Log");
    expect(labels).not.toContain("Settings");
    expect(labels).not.toContain("Staff");
  });

  it("renders the staff console without manager-only surfaces", () => {
    authAs("cafeteria_staff");
    render(<Sidebar />);
    const labels = navLabels();
    expect(labels).toContain("Menu");
    expect(labels).toContain("Orders");
    // Inventory is intentionally staff-visible (managerNavItems roles include
    // cafeteria_staff — Phase 58 Workstream D), but Reports is manager-only.
    expect(labels).toContain("Inventory");
    expect(labels).not.toContain("Daily Menu");
    expect(labels).not.toContain("Reports");
  });

  it("renders no dashboard navigation for a student", () => {
    authAs("student");
    render(<Sidebar />);
    expect(document.querySelectorAll("nav a")).toHaveLength(0);
  });

  it("renders no dashboard navigation for a logged-out user", () => {
    authAs(null);
    render(<Sidebar />);
    expect(document.querySelectorAll("nav a")).toHaveLength(0);
  });

  it("marks the active link with aria-current on the matching route", () => {
    authAs("university_admin");
    currentPath = "/dashboard/admin/users";
    render(<Sidebar />);

    const usersLink = screen
      .getAllByText("Users")
      .map((el) => el.closest("a"))
      .find((a) => a !== null);
    expect(usersLink).toHaveAttribute("aria-current", "page");

    // A different route must not be marked active.
    const homeLink = screen
      .getAllByText("Home")
      .map((el) => el.closest("a"))
      .find((a) => a !== null);
    expect(homeLink).not.toHaveAttribute("aria-current");
  });
});
