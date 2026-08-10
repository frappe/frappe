import { describe, expect, it } from "vitest";
import { BUILT_IN_KINDS, addableKinds, itemValues } from "../itemKinds";
import type { NavigationItemKind } from "../itemKinds";

const PAGE: NavigationItemKind = {
  type: "page",
  label: "Page",
  icon: "layout",
  field: "page",
  doctype: "Studio Page",
};

describe("addableKinds", () => {
  it("offers the framework's own kinds when the host adds none", () => {
    expect(addableKinds().map((kind) => kind.type)).toEqual(["link", "doctype"]);
  });

  it("appends the host's kinds after them", () => {
    expect(addableKinds([PAGE]).map((kind) => kind.type)).toEqual([
      "link",
      "doctype",
      "page",
    ]);
  });

  it("leaves the built-in list alone", () => {
    addableKinds([PAGE]);

    expect(BUILT_IN_KINDS).toHaveLength(2);
  });
});

describe("itemValues", () => {
  const values = { target: "/docs", label: "Docs", icon: "book" };

  it("puts the target in the field the kind names", () => {
    expect(itemValues(BUILT_IN_KINDS[0], values)).toEqual({
      type: "link",
      label: "Docs",
      icon: "book",
      url: "/docs",
    });
  });

  it("needs no case for a kind the framework has never heard of", () => {
    expect(itemValues(PAGE, { ...values, target: "crm-dashboard" })).toEqual({
      type: "page",
      label: "Docs",
      icon: "book",
      page: "crm-dashboard",
    });
  });
});
