/**
 * UniServe — Auth Layout
 *
 * Centered layout for login, register, and email verification pages.
 */
export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <main className="min-h-screen flex items-center justify-center bg-[var(--bg-secondary)] px-4 py-8">
      {children}
    </main>
  );
}
