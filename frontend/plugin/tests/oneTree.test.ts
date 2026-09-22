import { describe, expect, it } from "vitest";
import oneTree, {
  LINKED_UI,
  REAL_UI,
  frameworkPublishedFiles,
  outOfLinkedPackage,
} from "../oneTree.js";

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

describe("a framework name published from a file", () => {
  const manifest = [
    {
      app: "frappe",
      source_dir: "/bench/apps/frappe/frappe",
      import_map: { vue: "vue", "frappe/i18n": "./frontend/i18n.js" },
    },
    { app: "crm", source_dir: "/bench/apps/crm/crm", runtime_deps: {} },
  ];
  const plugin = oneTree(manifest) as any;

  it("lists only the scoped file values", () => {
    expect(frameworkPublishedFiles(manifest)).toEqual({
      "frappe/i18n": "/bench/apps/frappe/frappe/frontend/i18n.js",
    });
  });

  it("resolves from an app's source without a declaration", () => {
    expect(
      plugin.resolveId(
        "frappe/i18n",
        "/bench/apps/crm/crm/frontend/lib/index.js",
      ),
    ).toBe("/bench/apps/frappe/frappe/frontend/i18n.js");
  });

  it("resolves from the framework's own contributed source", () => {
    expect(
      plugin.resolveId(
        "frappe/i18n",
        "/bench/apps/frappe/frappe/core/doctype/user/frontend/record.js",
      ),
    ).toBe("/bench/apps/frappe/frappe/frontend/i18n.js");
  });

  it("does not reach an importer outside every app's source, such as ui/", () => {
    expect(
      plugin.resolveId("frappe/i18n", `${REAL_UI}/src/components/x.ts`),
    ).toBeUndefined();
  });

  it("still leaves an undeclared bare name to vite", () => {
    expect(
      plugin.resolveId("vue", "/bench/apps/crm/crm/frontend/lib/index.js"),
    ).toBeUndefined();
  });
});
