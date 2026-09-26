import type { Metadata } from "next";

import { AuthProvider } from "@/contexts/AuthContext";
import "./globals.css";

export const metadata: Metadata = {
  title: "UniServe — University Cafeteria Platform",
  description: "Order food from your university cafeteria",
};

/**
 * UniServe — Root Layout
 *
 * Wraps the app with AuthProvider for authentication state management.
 */
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-gray-50 text-gray-900 antialiased">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
