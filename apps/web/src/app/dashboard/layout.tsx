/**
 * UniServe — Dashboard Layout
 *
 * Placeholder layout for the authenticated dashboard area.
 * Navigation and role-based content will be added in future phases.
 */
export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen">
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <h1 className="text-lg font-semibold text-gray-800">UniServe</h1>
      </header>
      <main className="max-w-7xl mx-auto px-6 py-8">{children}</main>
    </div>
  );
}
