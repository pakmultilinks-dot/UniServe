import type { Metadata } from "next";

import { AuthProvider } from "@/contexts/AuthContext";

export const metadata: Metadata = {
  title: "UniServe — University Cafeteria Platform",
  description: "Order food from your university cafeteria",
};

/**
 * UniServe — Root Layout
 *
 * Wraps the app with AuthProvider for authentication state management.
 * Role-based layouts (cafeteria, university admin) will be added in future phases.
 */
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
