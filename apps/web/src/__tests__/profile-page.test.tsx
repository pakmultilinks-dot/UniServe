/**
 * Phase 60 (Workstream A) — Profile page behaviour tests.
 *
 * Asserts read-only rendering, edit/save flow, required-field validation,
 * and server-failure toasts.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, updateProfile: vi.fn() };
});

const refreshUserMock = vi.fn().mockResolvedValue(undefined);

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({
    user: {
      id: "u1",
      role: "cafeteria_manager",
      first_name: "Ayesha",
      last_name: "Khan",
      university_email: "ayesha.khan@lgu.edu.pk",
      university_id: "LGU-2024-001",
      category: "student",
      status: "active",
    },
    refreshUser: refreshUserMock,
    logout: vi.fn(),
  }),
}));

import * as api from "@/lib/api";
import ProfilePage from "@/app/dashboard/profile/page";
import { ToastProvider } from "@/components/ui/Toast";
import type { User } from "@uniserve/shared-types";

const apiMock = vi.mocked(api);

const PROFILE_USER: User = {
  id: "u1",
  first_name: "Ayesha",
  last_name: "Khan",
  university_id: "LGU-2024-001",
  university_email: "ayesha.khan@lgu.edu.pk",
  category: "student",
  role: "cafeteria_manager",
  status: "active",
  email_verified: true,
  created_at: "2025-01-01T00:00:00Z",
};

const setNativeValue = (el: HTMLInputElement, value: string) => {
  const setter = Object.getOwnPropertyDescriptor(
    HTMLInputElement.prototype,
    "value",
  )!.set!;
  setter.call(el, value);
  el.dispatchEvent(new Event("input", { bubbles: true }));
};

/** The edit form renders two plain text inputs (first name, last name). */
function editFormInputs(): HTMLInputElement[] {
  return screen
    .getAllByRole("textbox")
    .map((el) => el as HTMLInputElement);
}

function renderPage() {
  return render(
    <ToastProvider>
      <ProfilePage />
    </ToastProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  refreshUserMock.mockResolvedValue(undefined);
});

describe("ProfilePage — rendering", () => {
  it("renders the user's identity details read-only by default", () => {
    renderPage();

    expect(screen.getByText("Ayesha Khan")).toBeInTheDocument();
    // The email/ID render in both the avatar block and the details list.
    expect(
      screen.getAllByText("ayesha.khan@lgu.edu.pk").length,
    ).toBeGreaterThan(0);
    expect(
      screen.getAllByText("LGU-2024-001").length,
    ).toBeGreaterThan(0);
    expect(screen.getByText("Edit Profile")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Save Changes" }),
    ).not.toBeInTheDocument();
  });
});

describe("ProfilePage — edit and save flow", () => {
  it("validates required fields before calling the API", async () => {
    renderPage();

    fireEvent.click(screen.getByText("Edit Profile"));
    const [first, last] = editFormInputs();
    setNativeValue(first, "");
    setNativeValue(last, "");
    fireEvent.click(screen.getByRole("button", { name: "Save Changes" }));

    expect(
      await screen.findByText("First and last name are required"),
    ).toBeInTheDocument();
    expect(apiMock.updateProfile).not.toHaveBeenCalled();
  });

  it("saves trimmed names, refreshes the user, and confirms success", async () => {
    apiMock.updateProfile.mockResolvedValue(PROFILE_USER);
    renderPage();

    fireEvent.click(screen.getByText("Edit Profile"));
    const [first, last] = editFormInputs();
    setNativeValue(first, "  Ayesha Updated  ");
    setNativeValue(last, "Khan Updated");

    fireEvent.click(screen.getByRole("button", { name: "Save Changes" }));

    await waitFor(() =>
      expect(apiMock.updateProfile).toHaveBeenCalledWith({
        first_name: "Ayesha Updated",
        last_name: "Khan Updated",
      }),
    );
    expect(refreshUserMock).toHaveBeenCalled();
    expect(
      await screen.findByText("Profile updated successfully"),
    ).toBeInTheDocument();
  });

  it("surfaces server failures as an error toast and stays in edit mode", async () => {
    apiMock.updateProfile.mockRejectedValue(new Error("Server said no"));
    renderPage();

    fireEvent.click(screen.getByText("Edit Profile"));
    const [first, last] = editFormInputs();
    setNativeValue(first, "Ayesha");
    setNativeValue(last, "Khan");

    fireEvent.click(screen.getByRole("button", { name: "Save Changes" }));

    expect(await screen.findByText("Server said no")).toBeInTheDocument();
    // Still in edit mode — save failed, nothing was discarded.
    expect(
      screen.getByRole("button", { name: "Save Changes" }),
    ).toBeInTheDocument();
  });
});
