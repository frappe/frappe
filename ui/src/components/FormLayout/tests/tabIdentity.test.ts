import { describe, expect, it } from "vitest";
import { identifyTabs } from "../tabIdentity";

const identities = (tabs: { name?: string; label?: string }[]) =>
  identifyTabs(tabs).map((tab) => tab.identity);

describe("identifyTabs", () => {
  it("prefers the author's name", () => {
    expect(identities([{ name: "products", label: "Products" }])).toEqual([
      "products",
    ]);
  });

  it("falls back to the label, slugified", () => {
    expect(identities([{ label: "Product Details" }])).toEqual([
      "product-details",
    ]);
  });

  it("falls back to the position when there is neither", () => {
    expect(identities([{}, { label: "" }])).toEqual(["tab-1", "tab-2"]);
  });

  it("suffixes collisions deterministically", () => {
    const tabs = [
      { name: "details" },
      { label: "Details" },
      { name: "details" },
    ];
    expect(identities(tabs)).toEqual(["details", "details-2", "details-3"]);
  });

  it("does not hand out a suffix that is already someone's name", () => {
    // Two tabs would both like `details-2`: the author wrote one and the
    // de-duplicator wants the other. Every identity must still be distinct.
    const tabs = [{ name: "details" }, { name: "details-2" }, { name: "details" }];
    expect(new Set(identities(tabs)).size).toBe(3);
    expect(identities(tabs)).toEqual(["details", "details-2", "details-3"]);
  });

  it("numbers the positional fallback over the list it is given", () => {
    // `FormLayout` hands it the *whole* layout, hidden tabs included, so this
    // numbering does not shift when a `depends_on` neighbour disappears.
    expect(identities([{}, { label: "Named" }, {}])).toEqual([
      "tab-1",
      "named",
      "tab-3",
    ]);
  });

  it("keeps name meaning what the author wrote", () => {
    const [tab] = identifyTabs([{ label: "Product Details" }]);
    expect(tab.name).toBeUndefined();
    expect(tab.identity).toBe("product-details");
  });
});
