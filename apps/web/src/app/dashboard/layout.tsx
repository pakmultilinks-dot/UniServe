"use client";

import React, { useState } from "react";
import { Sidebar, MobileSidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";

/**
 * UniServe — Dashboard Layout
 *
 * Authenticated shell with sidebar navigation and header.
 * Responsive: full sidebar on desktop, hamburger + overlay on mobile.
 */
export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  return (
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
      <div className={`transition-all duration-300 ${sidebarCollapsed ? "lg:ml-[68px]" : "lg:ml-64"}`}>
        <Header onMenuToggle={() => setMobileSidebarOpen(true)} />
        <main className="p-4 sm:p-6 lg:p-8">
          {children}
        </main>
      </div>
    </div>
  );
}
