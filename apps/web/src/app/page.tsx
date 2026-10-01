/**
 * UniServe — Home Page
 *
 * Static-export-safe redirect to /dashboard (which handles auth checks and
 * redirects unauthenticated users to /login).
 *
 * IMPORTANT: `redirect()` from next/navigation CANNOT be used here — this app
 * builds with `output: "export"` (fully static hosting behind Caddy). During
 * export, `redirect()` throws and Next.js emits an error shell (`__next_error__`)
 * as index.html, which breaks the production landing page. A client-side
 * redirect is the supported pattern for static exports.
 */
"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/dashboard");
  }, [router]);

  return (
    <main
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: "12px",
        fontFamily: "system-ui, sans-serif",
      }}
    >
      <p>Redirecting to dashboard…</p>
      <p>
        <a href="/dashboard">Continue to dashboard</a>
      </p>
    </main>
  );
}
