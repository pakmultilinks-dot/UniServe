import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "UniServe — University Cafeteria Platform",
  description: "Order food from your university cafeteria",
};

/**
 * UniServe — Root Layout
 *
 * This is the entry point for the Next.js web application.
 * Role-based layouts (cafeteria, university admin) will be added in Phase 2+.
 */
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
