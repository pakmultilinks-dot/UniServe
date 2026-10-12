import type { Metadata } from "next";
import { AuthProvider } from "@/contexts/AuthContext";
import { ToastProvider } from "@/components/ui/Toast";
import "./globals.css";

export const metadata: Metadata = {
  title: "UniServe — LGU Cafeteria Platform",
  description:
    "Order ahead from Lahore Garrison University cafeterias. Browse daily menus, track your order live, and pick it up without waiting in line.",
  openGraph: {
    title: "UniServe — LGU Cafeteria Platform",
    description:
      "Skip the line. Order ahead from the Student and Faculty cafeterias at Lahore Garrison University.",
    type: "website",
    siteName: "UniServe",
  },
  twitter: {
    card: "summary",
    title: "UniServe — LGU Cafeteria Platform",
    description:
      "Skip the line. Order ahead from the Student and Faculty cafeterias at Lahore Garrison University.",
  },
};

/**
 * UniServe — Root Layout
 *
 * Wraps the app with AuthProvider for authentication state management
 * and ToastProvider for non-blocking notification toasts.
 */
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="scroll-smooth" suppressHydrationWarning>
      <head>
        {/* Inter via <link>: the CSS @import in globals.css sits after the
            Tailwind directives, where browsers may ignore it. */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap"
          rel="stylesheet"
        />
        {/* Inline script to apply theme before paint — prevents flash */}
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem("uniserve_theme");if(t==="dark"){document.documentElement.classList.add("dark")}else{document.documentElement.classList.remove("dark")}}catch(e){}})();`,
          }}
        />
      </head>
      <body className="bg-[var(--bg-primary)] text-[var(--text-primary)] font-sans antialiased min-h-screen">
        <AuthProvider>
          <ToastProvider>{children}</ToastProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
