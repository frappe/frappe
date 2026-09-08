import { describe, expect, it } from "vitest";
import { effectScope } from "vue";
import { setScoped } from "../scopedRegistry";

// `effectScope()` stands in for a component's setup scope: code run inside
// `scope.run()` sees it as the current scope, and `scope.stop()` fires the same
// disposal that unmount would — letting us test the auto-restore without mounting.
describe("setScoped", () => {
  it("overrides an existing entry, then restores it on scope dispose", () => {
    const map = new Map<string, number>([["A", 1]]);
    const scope = effectScope();

    scope.run(() => {
      expect(setScoped(map, "A", 2)).toBe(true);
      expect(map.get("A")).toBe(2); // override active
    });

    expect(map.get("A")).toBe(2); // still active after run, before dispose
    scope.stop();
    expect(map.get("A")).toBe(1); // restored to the snapshot
  });

  it("removes a newly-added entry on dispose (no prior value to restore)", () => {
    const map = new Map<string, number>();
    const scope = effectScope();

    scope.run(() => setScoped(map, "B", 9));
    expect(map.get("B")).toBe(9);

    scope.stop();
    expect(map.has("B")).toBe(false);
  });

  it("returns false and writes nothing when there is no active scope", () => {
    const map = new Map<string, number>([["A", 1]]);
    expect(setScoped(map, "A", 2)).toBe(false);
    expect(map.get("A")).toBe(1); // untouched — caller falls back to a global write
  });

  it("does not clobber a later write that superseded it", () => {
    const map = new Map<string, number>([["A", 1]]);
    const scope = effectScope();

    scope.run(() => setScoped(map, "A", 2));
    map.set("A", 3); // a later (e.g. global) registration wins

    scope.stop();
    expect(map.get("A")).toBe(3); // the newer write is preserved, not reverted to 1
  });

  it("independent scopes restore independently", () => {
    const map = new Map<string, number>([["A", 1]]);
    const outer = effectScope();
    const inner = effectScope();

    outer.run(() => setScoped(map, "A", 2));
    inner.run(() => setScoped(map, "A", 3));
    expect(map.get("A")).toBe(3);

    inner.stop();
    expect(map.get("A")).toBe(2); // inner reverts to what outer had set

    outer.stop();
    expect(map.get("A")).toBe(1); // outer reverts to the original
  });

  it("keeps the override while a later scope set the SAME value is still active", () => {
    // Two scopes register the *same* component — what an HMR reload does (the new
    // instance mounts and registers before the old one disposes), or the same
    // overriding component mounted twice. A naive snapshot/restore can't tell the
    // frames apart and would restore the base on the first dispose; the stack must
    // hold the override until the *last* scope using it goes away.
    const map = new Map<string, string>([["Link", "lib"]]);
    const a = effectScope();
    const b = effectScope();

    a.run(() => setScoped(map, "Link", "demo"));
    b.run(() => setScoped(map, "Link", "demo"));
    expect(map.get("Link")).toBe("demo");

    a.stop();
    expect(map.get("Link")).toBe("demo"); // b still relies on it — must NOT revert

    b.stop();
    expect(map.get("Link")).toBe("lib"); // last one out restores the base
  });
});
