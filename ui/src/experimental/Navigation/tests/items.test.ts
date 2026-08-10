import { describe, expect, it } from "vitest";
import { isAbsoluteUrl, isViewItem, itemTarget } from "../items";
import type { NavigationItem } from "../types";
import type { SavedView } from "../../SavedViews/types";

const ORIGIN = "https://crm.example.com";

function link(overrides: Partial<NavigationItem> = {}): NavigationItem {
  return {
    name: "row1",
    type: "link",
    label: "Docs",
    icon: "",
    dt: "",
    url: "/docs",
    new_tab: 0,
    hidden: 0,
    own: 0,
    view: null,
    ...overrides,
  };
}

describe("isViewItem", () => {
  it("tells a view from a link", () => {
    const view = { name: "1", label: "Open" } as SavedView;

    expect(isViewItem(link({ type: "view", view }))).toBe(true);
    expect(isViewItem(link())).toBe(false);
  });

  it("counts a doctype item as a non-view, so a section of them is extras", () => {
    expect(isViewItem(link({ type: "doctype", dt: "Note", url: "/Note" }))).toBe(
      false
    );
  });
});

describe("isAbsoluteUrl", () => {
  it("recognizes a URL that names its own origin", () => {
    expect(isAbsoluteUrl("https://frappe.io/docs")).toBe(true);
  });

  it("leaves a path, a hash and nothing to the router", () => {
    expect(isAbsoluteUrl("/crm/deals")).toBe(false);
    expect(isAbsoluteUrl("#settings/general")).toBe(false);
    expect(isAbsoluteUrl("")).toBe(false);
  });
});

describe("itemTarget", () => {
  it("routes a path inside the app", () => {
    expect(itemTarget(link({ url: "/crm/deals" }))).toEqual({ path: "/crm/deals" });
  });

  it("routes the settings hash, which opens over the current page", () => {
    expect(itemTarget(link({ url: "#settings/general" }))).toEqual({
      path: "#settings/general",
    });
  });

  it("leaves for another origin", () => {
    expect(itemTarget(link({ url: "https://frappe.io/docs" }))).toEqual({
      leave: "https://frappe.io/docs",
    });
  });

  it("leaves for this site's own absolute URL too, which the router cannot take", () => {
    expect(itemTarget(link({ url: `${ORIGIN}/crm/deals` }))).toEqual({
      leave: `${ORIGIN}/crm/deals`,
    });
  });

  it("routes a doctype item by the list route the server resolved for it", () => {
    expect(
      itemTarget(link({ type: "doctype", dt: "CRM Deal", url: "/CRM%20Deal" }))
    ).toEqual({ path: "/CRM%20Deal" });
  });

  it("leaves whenever a new tab was asked for, however internal the URL", () => {
    expect(itemTarget(link({ url: "/crm/deals", new_tab: 1 }))).toEqual({
      leave: "/crm/deals",
    });
  });
});
