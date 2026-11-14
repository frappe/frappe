// The inset the corner floats add to their right offset, and the toast viewport's rule for it.
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { navigationOvershoot } from "../navigationInset";

describe("the toast viewport", () => {
  it("adds the navigation's inset to sonner's right offset", () => {
    const css = readFileSync("src/index.css", "utf8");
    expect(css).toMatch(
      /\[data-sonner-toaster\]\[data-x-position="right"\]\s*\{\s*right: calc\(var\(--offset-right\) \+ var\(--shell-nav-inset-right, 0px\)\);/,
    );
  });
});

describe("navigationOvershoot", () => {
  it("is how far the float's right end reaches into the navigation", () => {
    expect(navigationOvershoot(940, 460, 1400, 320)).toBe(320);
    expect(navigationOvershoot(800, 460, 1400, 320)).toBe(180);
  });

  it("is nothing for a float clear of the navigation, or with no navigation on the right", () => {
    expect(navigationOvershoot(600, 460, 1400, 320)).toBe(0);
    expect(navigationOvershoot(940, 460, 1400, 0)).toBe(0);
  });

  it("never pulls the float's left end past the window's left edge", () => {
    // A float wider than the room beside the navigation stays at the left edge.
    expect(navigationOvershoot(200, 900, 1000, 320)).toBe(200);
    for (const left of [0, 100, 500, 940]) {
      expect(
        left - navigationOvershoot(left, 460, 1400, 320),
      ).toBeGreaterThanOrEqual(0);
    }
  });
});
