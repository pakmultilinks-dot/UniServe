const { PHASE_PRODUCTION_BUILD } = require("next/constants");

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Embed the source revision into every static export so operators can
  // distinguish an immutable old Vercel preview URL from the active build.
  env: {
    UNISERVE_BUILD_SHA: process.env.VERCEL_GIT_COMMIT_SHA || process.env.GITHUB_SHA || "local",
  },
  // Static export — works with Caddy serving _next/static/*
  output: "export",
  // API proxy for development only — disabled in production
  async rewrites() {
    if (process.env.NODE_ENV === "production") return [];
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8000/api/:path*",
      },
    ];
  },
};

module.exports = (phase) => {
  // C-1 hardening: NEXT_PUBLIC_* values are baked into the static export at
  // build time. A production build without NEXT_PUBLIC_API_URL would silently
  // ship every API call and every menu image pointed at the visitor's own
  // localhost. Fail loudly instead; development (`next dev`) is unaffected.
  if (phase === PHASE_PRODUCTION_BUILD && !process.env.NEXT_PUBLIC_API_URL) {
    throw new Error(
      "NEXT_PUBLIC_API_URL is not set. Production web builds must be built " +
        "with the real API origin, e.g. " +
        "NEXT_PUBLIC_API_URL=https://api.<yourdomain>/api/v1 npm run build. " +
        "Refusing to bake a localhost fallback into the static export."
    );
  }
  return nextConfig;
};
