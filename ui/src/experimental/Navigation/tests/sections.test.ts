import { describe, expect, it } from "vitest";
import {
  findExtrasSection,
  findFlatSection,
  findView,
  isExtrasSection,
  withExtrasLast,
} from "../sections";
import type { NavigationItem, NavigationSection } from "../types";
import type { SavedView } from "../../SavedViews/types";

function view(name: string): SavedView {
  return {
    name,
    label: `View ${name}`,
    reference_doctype: "Note",
    type: "list",
  };
}

function viewItem(name: string): NavigationItem {
  return {
    name,
    type: "view",
    label: "Open",
    icon: "",
    dt: "",
    url: "",
    new_tab: 0,
    hidden: 0,
    own: 0,
    view: view(name),
  };
}

function linkItem(name: string): NavigationItem {
  return {
    name,
    type: "link",
    label: "Docs",
    icon: "",
    dt: "",
    url: "/docs",
    new_tab: 0,
    hidden: 0,
    own: 0,
    view: null,
  };
}

function section(name: string, items: NavigationItem[]): NavigationSection {
  return { name, label: name, user: "", hidden: 0, items };
}

describe("findView", () => {
  const sections = [
    section("s1", [linkItem("r0"), viewItem("1")]),
    section("s2", [viewItem("2")]),
  ];

  it("finds a view across sections, looking past items that hold none", () => {
    expect(findView(sections, "2")?.name).toBe("2");
  });

  it("matches a numeric route param against an autoincrement name", () => {
    expect(findView(sections, 1)?.name).toBe("1");
  });

  it("returns undefined for an unknown or absent id", () => {
    expect(findView(sections, "99")).toBeUndefined();
    expect(findView(sections, null)).toBeUndefined();
  });
});

describe("isExtrasSection", () => {
  it("is true for a section of nothing but links", () => {
    expect(
      isExtrasSection(section("More", [linkItem("a"), linkItem("b")]))
    ).toBe(true);
  });

  it("is false as soon as one view is in it", () => {
    expect(
      isExtrasSection(section("Views", [linkItem("a"), viewItem("b")]))
    ).toBe(false);
  });

  it("is true for an empty section, which has no views either", () => {
    expect(isExtrasSection(section("New", []))).toBe(true);
  });
});

describe("findExtrasSection", () => {
  const mine = (name: string, items: NavigationItem[]) => ({
    ...section(name, items),
    user: "someone@example.com",
  });

  it("finds the caller's own extras block for a Just-me add", () => {
    const sections = [section("More", [linkItem("a")]), mine("Mine", [linkItem("b")])];

    expect(findExtrasSection(sections, false)?.name).toBe("Mine");
  });

  it("finds the shared one when the add is for everyone", () => {
    const sections = [section("More", [linkItem("a")]), mine("Mine", [linkItem("b")])];

    expect(findExtrasSection(sections, true)?.name).toBe("More");
  });

  it("looks past a section holding views, which a link does not belong in", () => {
    const sections = [mine("Views", [viewItem("a")]), mine("Mine", [linkItem("b")])];

    expect(findExtrasSection(sections, false)?.name).toBe("Mine");
  });

  it("is undefined when the scope has none, which is what makes the caller create one", () => {
    expect(findExtrasSection([section("Views", [viewItem("a")])], true)).toBeUndefined();
  });

  it("prefers a filled extras block to a section somebody just added", () => {
    const sections = [mine("New section", []), mine("More", [linkItem("a")])];

    expect(findExtrasSection(sections, false)?.name).toBe("More");
  });

  it("falls back to an empty section when that is all the scope has", () => {
    expect(findExtrasSection([mine("New section", [])], false)?.name).toBe("New section");
  });
});

describe("findFlatSection", () => {
  const mine = (name: string, items: NavigationItem[]) => ({
    ...section(name, items),
    user: "someone@example.com",
  });

  it("takes the last section, so the item lands at the bottom of the one list", () => {
    const sections = [section("Views", [viewItem("a")]), mine("Mine", [linkItem("b")])];

    expect(findFlatSection(sections, false)?.name).toBe("Mine");
  });

  it("drops an item of the caller's own among the views, having no block to keep it out of", () => {
    expect(findFlatSection([section("Views", [viewItem("a")])], false)?.name).toBe(
      "Views"
    );
  });

  it("needs a shared section for an add that is for everyone", () => {
    const sections = [section("Views", [viewItem("a")]), mine("Mine", [linkItem("b")])];

    expect(findFlatSection(sections, true)?.name).toBe("Views");
  });

  it("is undefined on an empty sidebar, which is what makes the caller create one", () => {
    expect(findFlatSection([], false)).toBeUndefined();
    expect(findFlatSection([mine("Mine", [])], true)).toBeUndefined();
  });
});

describe("withExtrasLast", () => {
  const views = section("Views", [viewItem("a")]);
  const pipeline = section("Pipeline", [viewItem("b")]);
  const extras = section("More", [linkItem("c")]);

  it("sinks an extras section below the views", () => {
    expect(withExtrasLast([extras, views]).map((s) => s.name)).toEqual([
      "Views",
      "More",
    ]);
  });

  it("leaves the view sections in the order the server sent", () => {
    expect(
      withExtrasLast([views, extras, pipeline]).map((s) => s.name)
    ).toEqual(["Views", "Pipeline", "More"]);
  });

  it("keeps several extras sections in their own order", () => {
    const other = section("Help", [linkItem("d")]);

    expect(withExtrasLast([extras, views, other]).map((s) => s.name)).toEqual([
      "Views",
      "More",
      "Help",
    ]);
  });

  it("changes nothing when every section holds a view", () => {
    expect(withExtrasLast([views, pipeline]).map((s) => s.name)).toEqual([
      "Views",
      "Pipeline",
    ]);
  });
});
