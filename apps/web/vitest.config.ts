import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
import path from "node:path";

// npm workspaces hoists React 19 (mobile workspace) to the repo root while
// apps/web pins React 18 in its own node_modules. Native dependency loading
// (e.g. @testing-library, hoisted to the root) therefore always reaches the
// root React 19 react-dom. Instead of fighting native resolution, run the
// whole test graph against the root React 19 runtime so there is exactly one
// React copy in the test environment. Production builds are unaffected —
// Next.js resolves React from apps/web's own node_modules as before.
const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const rootRequire = createRequire(path.join(rootDir, "package.json"));
const rootReact = path.dirname(rootRequire.resolve("react/package.json"));
const rootReactDom = path.dirname(rootRequire.resolve("react-dom/package.json"));

export default defineConfig({
  // Cast: @vitejs/plugin-react resolves its `vite` types from the hoisted
  // root vite copy, while vitest 2.1.9 carries its own nested vite — the
  // plugin instances are structurally identical but nominally incompatible.
  // Runtime behaviour is unaffected; the cast only silences the d.ts skew.
  plugins: [react() as never],
  resolve: {
    alias: [
      { find: /^react$/, replacement: rootReact },
      { find: /^react-dom$/, replacement: rootReactDom },
      { find: /^react\/jsx-runtime$/, replacement: path.join(rootReact, "jsx-runtime") },
      { find: /^react\/jsx-dev-runtime$/, replacement: path.join(rootReact, "jsx-dev-runtime") },
      { find: /^react-dom\/client$/, replacement: path.join(rootReactDom, "client") },
      { find: /^react-dom\/jsx-runtime$/, replacement: path.join(rootReactDom, "jsx-runtime") },
      { find: /^react-dom\/jsx-dev-runtime$/, replacement: path.join(rootReactDom, "jsx-dev-runtime") },
      { find: /^react-dom\/test-utils$/, replacement: path.join(rootReactDom, "test-utils") },
      { find: "@uniserve/shared-types", replacement: fileURLToPath(new URL("../../packages/shared-types/src/index.ts", import.meta.url)) },
      { find: "@", replacement: fileURLToPath(new URL("./src", import.meta.url)) },
    ],
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
