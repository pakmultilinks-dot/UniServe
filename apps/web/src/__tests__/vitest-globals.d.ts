/**
 * Phase 60 — jest-dom matcher types for apps/web's OWN vitest instance.
 *
 * Why this file exists instead of `import "@testing-library/jest-dom/vitest"`:
 * the jest-dom "vitest" entrypoint declares `declare module "vitest"` inside
 * its own package. TypeScript resolves that module specifier relative to the
 * AUGMENTING file — i.e. the hoisted vitest 4 at the repo root — so the
 * matcher augmentation lands on the wrong Assertion interface and apps/web's
 * nested vitest 2.1.9 assertions never gain `toBeInTheDocument` etc.
 *
 * This d.ts sits inside apps/web, imports "vitest" first (making it a module
 * and pinning resolution to apps/web/node_modules/vitest), then augments that
 * exact interface. Runtime registration is separate — see vitest.setup.ts
 * (expect.extend of the standalone matchers, which resolves the correct
 * module instance at runtime).
 */

import "vitest";
import type { TestingLibraryMatchers } from "@testing-library/jest-dom/matchers";

declare module "vitest" {
  interface Assertion<T = any> extends TestingLibraryMatchers<any, T> {}
  interface AsymmetricMatchersContaining
    extends TestingLibraryMatchers<any, any> {}
}
