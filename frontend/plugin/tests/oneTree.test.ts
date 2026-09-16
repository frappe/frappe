import { describe, expect, it } from "vitest";
import { LINKED_UI, REAL_UI, outOfLinkedPackage } from "../oneTree.js";

const importer = `${LINKED_UI}/src/components/Phone/utils.ts`;

describe("a relative import that climbs out of the linked ui package", () => {
  it("resolves against the package's real place in the framework's tree", () => {
    expect(
      outOfLinkedPackage("../../../../frappe/geo/country_info.json", importer),
    ).toBe(`${REAL_UI}/../frappe/geo/country_info.json`.replace("ui/../", ""));
  });

  it("leaves a relative import inside the package to vite", () => {
    expect(outOfLinkedPackage("../Link/Link.vue", importer)).toBeUndefined();
  });

  it("leaves other importers alone", () => {
    expect(
      outOfLinkedPackage(
        "../../../../frappe/geo/country_info.json",
        `${REAL_UI}/src/x.ts`,
      ),
    ).toBeUndefined();
  });

  it("returns nothing for a file the tree does not have, so vite reports the miss", () => {
    expect(
      outOfLinkedPackage("../../../../frappe/geo/missing.json", importer),
    ).toBeUndefined();
  });
});
