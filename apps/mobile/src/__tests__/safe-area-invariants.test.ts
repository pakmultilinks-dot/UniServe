/**
 * Phase 4 — layout invariants that guard the Phase 3 clipping fixes.
 *
 * These are source-level invariants rather than rendered-layout assertions:
 * this repo has no React Native render harness, and safe-area geometry
 * cannot be exercised in a unit test. What CAN be pinned mechanically is
 * the structural contract the fixes rely on, so a later edit cannot silently
 * reintroduce the defect.
 *
 * Two regressions were caught this way and fixed in Phase 4:
 *   1. `styles.header` lost `paddingHorizontal`/`paddingVertical`, leaving
 *      the sheet title flush against the sheet edge.
 *   2. `paddingHorizontal` was applied to BOTH the ScrollView's own style
 *      and its `contentContainerStyle`, doubling the sheet body inset to 40.
 *
 * The mobile tsconfig does not include node types (and dependencies must not
 * be added just for a test), so `fs`/`path` are declared structurally below.
 */

interface FsLike {
  readFileSync(relativePath: string, encoding: "utf8"): string;
  readdirSync(absolutePath: string): string[];
}

interface PathLike {
  join(...parts: string[]): string;
  resolve(...parts: string[]): string;
}

declare function require(id: "fs"): FsLike;
declare function require(id: "path"): PathLike;
declare const __dirname: string;

const fs: FsLike = require("fs");
const path: PathLike = require("path");

const APP_ROOT = path.resolve(__dirname, "..", "..");
const read = (relativePath: string) =>
  fs.readFileSync(path.join(APP_ROOT, ...relativePath.split("/")), "utf8");

const TAB_SCREENS = fs
  .readdirSync(path.join(APP_ROOT, "app", "(app)", "(tabs)"))
  .filter((name) => name.endsWith(".tsx") && name !== "_layout.tsx")
  .sort();

describe("tab screens honour the top safe-area inset", () => {
  it("is applied to every tab screen (and none are added/removed silently)", () => {
    expect(TAB_SCREENS).toEqual([
      "cart.tsx",
      "favorites.tsx",
      "index.tsx",
      "notifications.tsx",
      "orders.tsx",
      "profile.tsx",
    ]);
  });

  TAB_SCREENS.forEach((file) => {
    it(`${file} wraps its root in SafeAreaView edges={["top"]}`, () => {
      const src = read(`app/(app)/(tabs)/${file}`);

      expect(src).toContain('from "react-native-safe-area-context"');
      expect(src).toContain('edges={["top"]}');
    });
  });
});

describe("BottomSheet content cannot be silently clipped", () => {
  const src = read(path.join("src", "components", "ui", "BottomSheet.tsx"));

  it("scrolls capped content instead of clipping it", () => {
    // A plain View under a maxHeight silently clips on Android (overflow
    // defaults to hidden), cutting off buttons with no way to reach them.
    expect(src).toMatch(/<ScrollView[^>]*style=\{styles\.content\}/);
    expect(src).not.toMatch(/<View style=\{styles\.content\}>/);
  });

  it("keeps the sheet body horizontal inset applied exactly once", () => {
    // Padding on a ScrollView's own `style` applies once. Repeating it on
    // contentContainerStyle would inset the body twice (20 -> 40). Match the
    // prop form so the explanatory comments in the component don't trip it.
    expect(src).not.toMatch(/contentContainerStyle=\{/);
    expect(src).not.toContain("contentInner");
  });

  it("keeps the header padded so the title is not flush with the edge", () => {
    const header = src.match(/header:\s*\{[\s\S]*?\n {2}\},/)?.[0] ?? "";

    expect(header).toContain("paddingHorizontal: 20");
    expect(header).toContain("paddingVertical: 12");
    // The header is a single title row; a screen-height cap here is an
    // editing accident, not a deliberate constraint.
    expect(header).not.toContain("maxHeight");
  });
});

describe("notification bodies stay fully readable", () => {
  it("does not truncate the body (there is no detail screen to recover it)", () => {
    const src = read(path.join("app", "(app)", "(tabs)", "notifications.tsx"));

    expect(src).not.toContain("numberOfLines={2}");
  });
});
