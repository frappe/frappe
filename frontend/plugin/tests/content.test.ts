import { describe, expect, it } from "vitest";
import { appContent, publishedFolders } from "../content.js";

const manifest = [
  {
    app: "frappe",
    source_dir: "/bench/apps/frappe/frappe",
    import_map: { vue: "vue", "frappe-ui": "frappe-ui" },
  },
  {
    app: "crm",
    source_dir: "/bench/apps/crm/crm",
    import_map: {
      "crm/ui": "@frappe/crm-ui",
      "crm/lib": "./lib/index.js",
      "crm/cards": "/lib/cards/index.js",
    },
  },
];

describe("the stylesheet's content list", () => {
  it("scans a published file's own folder, wherever it sits in the app", () => {
    expect(publishedFolders(manifest)).toEqual([
      "/bench/apps/crm/crm/lib",
      "/bench/apps/crm/crm/lib/cards",
    ]);
    expect(appContent(manifest)).toContain(
      "/bench/apps/crm/crm/lib/**/*.{vue,js,ts,jsx,tsx}",
    );
  });

  it("scans nothing for a published package: the package ships its own CSS", () => {
    expect(appContent(manifest).join("\n")).not.toContain("crm-ui");
  });

  it("keeps every app's frontend/ and custom/ folders", () => {
    expect(appContent(manifest)).toContain(
      "/bench/apps/crm/crm/**/frontend/**/*.{vue,js,ts,jsx,tsx}",
    );
    expect(appContent(manifest)).toContain(
      "/bench/apps/crm/crm/**/custom/**/*.{vue,js,ts,jsx,tsx}",
    );
  });

  it("never scans public/, which is compiled output", () => {
    expect(appContent(manifest)).toContain("!/bench/apps/crm/crm/**/public/**");
    expect(appContent(manifest)).toContain(
      "!/bench/apps/frappe/frappe/**/public/**",
    );
  });

  it("scans a folder once however many files it publishes", () => {
    const twice = [
      {
        app: "crm",
        source_dir: "/bench/apps/crm/crm",
        import_map: { "crm/a": "./lib/a.js", "crm/b": "./lib/b.js" },
      },
    ];
    expect(publishedFolders(twice)).toEqual(["/bench/apps/crm/crm/lib"]);
  });
});
