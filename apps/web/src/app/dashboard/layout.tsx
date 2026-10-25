"use client";

import React, { useState } from "react";
import { Sidebar, MobileSidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";
import { RoleGuard } from "@/components/RoleGuard";

/**
 * UniServe — Dashboard Layout
 *
 * Authenticated shell with sidebar navigation and header.
 * Responsive: full sidebar on desktop, hamburger + overlay on mobile.
 *
 * The entire /dashboard/* tree is wrapped in RoleGuard so only
 * university_admin, cafeteria_manager, and cafeteria_staff can render it.
 * Students and faculty are redirected to /mobile-required before any
 * dashboard content is shown.
 */
export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  return (
    <RoleGuard>
    <div className="min-h-screen">
      {/* Desktop sidebar */}
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      {/* Mobile sidebar */}
      <MobileSidebar
        open={mobileSidebarOpen}
        onClose={() => setMobileSidebarOpen(false)}
      />

      {/* Main content area — offset by sidebar width on desktop */}
      <div className={`min-w-0 transition-all duration-300 ${sidebarCollapsed ? "lg:ml-[68px]" : "lg:ml-64"}`}>
        <Header onMenuToggle={() => setMobileSidebarOpen(true)} />
        <main className="min-w-0 max-w-full overflow-x-clip p-4 sm:p-6 lg:p-8">
          {children}
        </main>
      </div>
    </div>
    </RoleGuard>
  );
}
