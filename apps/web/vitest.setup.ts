import * as matchers from "@testing-library/jest-dom/matchers";
import { expect, afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

// Register jest-dom matchers on THIS vitest instance's expect. The
// "@testing-library/jest-dom/vitest" shortcut calls expect.extend on the
// vitest copy IT resolves natively — hoisted at the repo root — which is a
// different module instance than apps/web's own vitest, so the matchers
// never land on the running runner's expect. (Matcher TYPE augmentation
// lives in src/__tests__/vitest-globals.d.ts for the same instance reason.)
expect.extend(matchers);

afterEach(() => {
  cleanup();
});
