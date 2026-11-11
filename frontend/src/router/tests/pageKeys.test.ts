import { describe, expect, it } from "vitest";
import { pageKeys } from "@/router/mainPage";

describe("the key of a declared page", () => {
  it("follows the record, so another record remounts the page", () => {
    const keyOf = pageKeys();

    const first = keyOf({ doctype: "Note", name: "A" });

    expect(keyOf({ doctype: "Note", name: "B" })).not.toBe(first);
    expect(keyOf({ doctype: "ToDo", name: "B" })).not.toBe(first);
  });

  it("keeps the key of a new record's page once it is saved and the address says so", () => {
    const keyOf = pageKeys();
    const unsaved = keyOf({ doctype: "Note", name: null });

    expect(keyOf({ doctype: "Note", name: "N-1" }, true)).toBe(unsaved);
    // A render with the same address again does not remount it.
    expect(keyOf({ doctype: "Note", name: "N-1" })).toBe(unsaved);
    expect(keyOf({ doctype: "Note", name: "N-2" })).not.toBe(unsaved);
  });

  it("remounts for any other move from a new record's page", () => {
    const keyOf = pageKeys();
    const unsaved = keyOf({ doctype: "Note", name: null });

    expect(keyOf({ doctype: "Note", name: "N-1" })).not.toBe(unsaved);
    expect(keyOf({ doctype: "ToDo", name: "T-1" }, true)).not.toBe(unsaved);
  });

  it("remounts a new record's page opened after the saved one kept its key", () => {
    const keyOf = pageKeys();
    const unsaved = keyOf({ doctype: "Note", name: null });
    keyOf({ doctype: "Note", name: "N-1" }, true);

    expect(keyOf({ doctype: "Note", name: null })).not.toBe(unsaved);
  });
});
