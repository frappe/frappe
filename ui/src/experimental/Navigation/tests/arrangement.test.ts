import { describe, expect, it } from "vitest";
import {
  canEditItem,
  canEditSection,
  findSourceSection,
  flipsVisibility,
  holdsItem,
  toBoxedRows,
  toRows,
  withHidden,
} from "../arrangement";
import type { NavigationItem, NavigationSection } from "../types";
import type { SavedView } from "../../SavedViews/types";

function item(name: string, hidden: 0 | 1 = 0): NavigationItem {
  return {
    name,
    type: "view",
    label: `View ${name}`,
    icon: "",
    dt: "",
    url: "",
    new_tab: 0,
    hidden,
    own: 0,
    view: {
      name,
      label: `View ${name}`,
      reference_doctype: "Note",
      type: "list",
    } as SavedView,
  };
}

function link(name: string): NavigationItem {
  return { ...item(name), type: "link", url: "/docs", view: null };
}

function section(user: string): NavigationSection {
  return { name: "s", label: "Views", user, hidden: 0, items: [] };
}

const SHARED = section("");
const PERSONAL = section("someone@example.com");

describe("toRows", () => {
  it("keeps the rendered order", () => {
    expect(toRows([item("2"), item("1")]).map((row) => row.name)).toEqual([
      "2",
      "1",
    ]);
  });

  it("carries the hidden flag through", () => {
    expect(toRows([item("1", 1)])).toEqual([{ name: "1", hidden: 1 }]);
  });

  it("names an item that holds no view just the same", () => {
    expect(toRows([link("1")])).toEqual([{ name: "1", hidden: 0 }]);
  });
});

describe("withHidden", () => {
  it("sets the flag on the named item only", () => {
    expect(withHidden([item("1"), item("2")], "2", true)).toEqual([
      { name: "1", hidden: 0 },
      { name: "2", hidden: 1 },
    ]);
  });

  it("unhides too, which is how edit mode restores an item", () => {
    expect(withHidden([item("1", 1)], "1", false)).toEqual([
      { name: "1", hidden: 0 },
    ]);
  });

  it("hides a link, which has no view to be found by", () => {
    expect(withHidden([link("1")], "1", true)).toEqual([
      { name: "1", hidden: 1 },
    ]);
  });

  it("leaves the rows alone when the item is not in them", () => {
    expect(withHidden([item("1")], "9", true)).toEqual([
      { name: "1", hidden: 0 },
    ]);
  });
});

describe("toBoxedRows", () => {
  it("reads the flag off the box a row is in, not off the row", () => {
    expect(toBoxedRows([item("1", 1)], [item("2", 0)])).toEqual([
      { name: "1", hidden: 0 },
      { name: "2", hidden: 1 },
    ]);
  });

  it("keeps each box's order and puts the hidden ones last", () => {
    const rows = toBoxedRows([item("2"), item("1")], [item("4"), item("3")]);

    expect(rows.map((row) => row.name)).toEqual(["2", "1", "4", "3"]);
  });

  it("is the whole section even when one box is empty", () => {
    expect(toBoxedRows([link("1")], [])).toEqual([{ name: "1", hidden: 0 }]);
    expect(toBoxedRows([], [link("1")])).toEqual([{ name: "1", hidden: 1 }]);
  });
});

describe("holdsItem", () => {
  const held = { ...SHARED, items: [item("1")] };
  const other = { ...PERSONAL, name: "s2", items: [item("2")] };

  it("is true for a row the section already had — a drop that changed box", () => {
    expect(holdsItem([held, other], held, item("1"))).toBe(true);
  });

  it("is false for a row from another section — a drop that changed section", () => {
    expect(holdsItem([held, other], held, item("2"))).toBe(false);
  });

  it("is false for a section the arrangement no longer names", () => {
    expect(holdsItem([other], held, item("1"))).toBe(false);
  });
});

describe("flipsVisibility", () => {
  it("is true across the shared/personal line", () => {
    expect(flipsVisibility(SHARED, PERSONAL)).toBe(true);
    expect(flipsVisibility(PERSONAL, SHARED)).toBe(true);
  });

  it("is false between two shared sections", () => {
    expect(flipsVisibility(SHARED, section(""))).toBe(false);
  });

  it("is false between two of the user's own sections", () => {
    expect(flipsVisibility(PERSONAL, section("someone@example.com"))).toBe(
      false
    );
  });
});

describe("findSourceSection", () => {
  const shared: NavigationSection = {
    ...SHARED,
    name: "s1",
    items: [item("1")],
  };
  const personal: NavigationSection = {
    ...PERSONAL,
    name: "s2",
    items: [item("2")],
  };

  it("finds the section that still lists the dropped item", () => {
    expect(
      findSourceSection([shared, personal], item("1"), personal)?.name
    ).toBe("s1");
  });

  it("never returns the destination, which now lists it too", () => {
    const landed = { ...personal, items: [item("2"), item("1")] };

    expect(findSourceSection([shared, landed], item("1"), landed)?.name).toBe(
      "s1"
    );
  });

  it("is undefined for a reorder inside one section", () => {
    expect(findSourceSection([shared], item("1"), shared)).toBeUndefined();
  });
});

describe("canEditSection", () => {
  it("lets anyone shape their own section", () => {
    expect(canEditSection(PERSONAL, false)).toBe(true);
  });

  it("holds a shared section back until the scope is Everyone", () => {
    expect(canEditSection(SHARED, false)).toBe(false);
    expect(canEditSection(SHARED, true)).toBe(true);
  });
});

describe("canEditItem", () => {
  const own = { ...link("mine"), own: 1 as const };

  it("follows the section for a row the section holds", () => {
    expect(canEditItem(SHARED, link("theirs"), false)).toBe(false);
    expect(canEditItem(SHARED, link("theirs"), true)).toBe(true);
    expect(canEditItem(PERSONAL, link("theirs"), false)).toBe(true);
  });

  it("frees a row of the user's own inside a shared section", () => {
    expect(canEditItem(SHARED, own, false)).toBe(true);
  });
});
