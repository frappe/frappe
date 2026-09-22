import { describe, expect, it } from "vitest";
import importMap, {
  builtImports,
  chunkName,
  devImports,
  importMapTag,
  isFileValue,
  publishedChunks,
  publishedStyling,
  publishedTargets,
  sizeReport,
  stylesheetTags,
} from "../importMap.js";

const base = "/assets/frappe/frontend/";

const FRAMEWORK = ["vue", "vue-router", "frappe-ui", "@framework/ui"];

// What Python writes: frappe's own entry carries the four bare names, an app's its scoped ones.
const manifest = [
  {
    app: "frappe",
    source_dir: "/bench/apps/frappe/frappe",
    import_map: Object.fromEntries(FRAMEWORK.map((name) => [name, name])),
  },
  {
    app: "crm",
    source_dir: "/bench/apps/crm/crm",
    import_map: {
      "crm/ui": "@frappe/crm-ui",
      "crm/lib": "./frontend/lib/index.js",
    },
  },
];
const PUBLISHED = [...FRAMEWORK, "crm/ui", "crm/lib"];

function bundleWith(
  names: string[],
  css: string[] = [],
  imports: string[] = [],
) {
  return Object.fromEntries(
    names.map((name) => [
      `assets/${chunkName(name)}-abc123.js`,
      {
        facadeModuleId: `\0published:${name}`,
        fileName: `assets/${chunkName(name)}-abc123.js`,
        viteMetadata: { importedCss: new Set(css) },
        imports,
      },
    ]),
  );
}

function withSharedChunk(bundle: Record<string, any>, css: string) {
  return {
    ...bundle,
    "assets/shared-1.js": {
      fileName: "assets/shared-1.js",
      viteMetadata: { importedCss: new Set([css]) },
      imports: ["assets/shared-2.js"],
    },
    // A cycle, so the walk must remember where it has been.
    "assets/shared-2.js": {
      fileName: "assets/shared-2.js",
      viteMetadata: { importedCss: new Set([css]) },
      imports: ["assets/shared-1.js"],
    },
  };
}

function plugin(command: "build" | "serve", logger: any = { info() {} }) {
  const p = importMap(manifest) as any;
  p.configResolved({ base, command, logger });
  return p;
}

describe("the published import map", () => {
  it("takes its names from the manifest, in apps.txt order", () => {
    expect(Object.keys(publishedTargets(manifest))).toEqual(PUBLISHED);
  });

  it("roots a file value at the app's source dir and leaves a package value bare", () => {
    expect(publishedTargets(manifest)["crm/lib"]).toBe(
      "/bench/apps/crm/crm/frontend/lib/index.js",
    );
    expect(publishedTargets(manifest)["crm/ui"]).toBe("@frappe/crm-ui");
    expect(
      publishedTargets([
        { source_dir: "/x", import_map: { "a/b": "/lib.js" } },
      ]),
    ).toEqual({
      "a/b": "/x/lib.js",
    });
    expect(isFileValue("./x")).toBe(true);
    expect(isFileValue("/x")).toBe(true);
    expect(isFileValue("@scope/pkg")).toBe(false);
  });

  it("refuses a manifest written before the hook existed, naming the fix", () => {
    expect(() => importMap([{ app: "frappe", source_dir: "/f" }])).toThrow(
      "predates the import_map hook",
    );
  });

  it("publishes nothing for an app whose entry has no import_map", () => {
    expect(publishedTargets([{ app: "gameplan", source_dir: "/g" }])).toEqual(
      {},
    );
  });

  it("gives an app's name a chunk and a map line, beside the framework's four", () => {
    const emitted: any[] = [];
    plugin("build").buildStart.call({
      emitFile: (file: unknown) => emitted.push(file),
    });
    expect(emitted.map((file) => file.name)).toContain("published-crm-lib");
    const bundle = bundleWith(PUBLISHED);
    const result = plugin("build").transformIndexHtml.handler("<html></html>", {
      bundle,
    });
    expect(JSON.parse(result.tags[0].children).imports["crm/lib"]).toBe(
      `${base}assets/published-crm-lib-abc123.js`,
    );
  });

  it("prints the size of each published name's chunk and the css it reaches", () => {
    const lines: string[] = [];
    const bundle = {
      ...bundleWith(PUBLISHED, ["assets/published-x.css"]),
      "assets/published-x.css": {
        fileName: "assets/published-x.css",
        source: "x".repeat(1500),
      },
    };
    for (const chunk of Object.values(bundle) as any[])
      chunk.code = "y".repeat(2000);
    plugin("build", {
      info: (line: string) => lines.push(line),
    }).generateBundle({}, bundle);
    expect(lines).toHaveLength(PUBLISHED.length);
    expect(lines.at(-1)).toBe(
      `published ${"crm/lib".padEnd(24)} 2.00 kB js + 1.50 kB css [styles: scanned]`,
    );
    expect(lines.at(-2)).toBe(
      `published ${"crm/ui".padEnd(24)} 2.00 kB js + 1.50 kB css [styles: yours]`,
    );
    expect(
      sizeReport(
        publishedChunks(bundleWith(["vue"]), ["vue"]),
        bundleWith(["vue"]),
      ),
    ).toEqual([`published ${"vue".padEnd(24)} 0.00 kB js`]);
  });

  it("says who styles each name: the build scans a file, a package ships its own CSS", () => {
    expect(publishedStyling(manifest)).toEqual({
      vue: "scanned",
      "vue-router": "scanned",
      "frappe-ui": "scanned",
      "@framework/ui": "scanned",
      "crm/ui": "yours",
      "crm/lib": "scanned",
    });
  });

  it("points each name at its emitted chunk under the build's base", () => {
    expect(
      builtImports(publishedChunks(bundleWith(PUBLISHED), PUBLISHED), base),
    ).toEqual({
      vue: `${base}assets/published-vue-abc123.js`,
      "vue-router": `${base}assets/published-vue-router-abc123.js`,
      "frappe-ui": `${base}assets/published-frappe-ui-abc123.js`,
      "@framework/ui": `${base}assets/published-framework-ui-abc123.js`,
      "crm/ui": `${base}assets/published-crm-ui-abc123.js`,
      "crm/lib": `${base}assets/published-crm-lib-abc123.js`,
    });
  });

  it("spells a scoped name without its punctuation", () => {
    expect(chunkName("@framework/ui")).toBe("published-framework-ui");
  });

  it("fails the build when a name has no chunk, so the page never ships a map with a hole", () => {
    expect(() =>
      publishedChunks(bundleWith(["vue", "frappe-ui"]), FRAMEWORK),
    ).toThrow("no entry chunk emitted for vue-router");
  });

  it("links a published chunk's stylesheet once, so a script-imported component is styled", () => {
    const bundle = bundleWith(PUBLISHED, ["assets/published-x.css"]);
    expect(
      stylesheetTags(publishedChunks(bundle, PUBLISHED), bundle, base),
    ).toEqual([
      {
        tag: "link",
        attrs: {
          rel: "stylesheet",
          crossorigin: true,
          href: `${base}assets/published-x.css`,
        },
        injectTo: "head",
      },
    ]);
    const bare = bundleWith(PUBLISHED);
    expect(
      stylesheetTags(publishedChunks(bare, PUBLISHED), bare, base),
    ).toEqual([]);
  });

  it("links the stylesheets of the chunks a published chunk imports, through a cycle", () => {
    const bundle = withSharedChunk(
      bundleWith(PUBLISHED, [], ["assets/shared-1.js"]),
      "assets/shared.css",
    );
    const hrefs = stylesheetTags(
      publishedChunks(bundle, PUBLISHED),
      bundle,
      base,
    ).map((tag) => tag.attrs.href);
    expect(hrefs).toEqual([`${base}assets/shared.css`]);
  });

  it("skips a stylesheet the document already links", () => {
    const bundle = bundleWith(PUBLISHED, ["assets/published-x.css"]);
    const html = `<link rel="stylesheet" href="${base}assets/published-x.css">`;
    expect(
      stylesheetTags(publishedChunks(bundle, PUBLISHED), bundle, base, html),
    ).toEqual([]);
  });

  it("serves the dev map from stable virtual ids", () => {
    expect(devImports(["vue"]).vue).toBe("/@id/__x00__published:vue");
  });

  it("emits one entry chunk per name at build start, and none on the dev server", () => {
    const emitted: unknown[] = [];
    const context = { emitFile: (file: unknown) => emitted.push(file) };
    plugin("serve").buildStart.call(context);
    expect(emitted).toEqual([]);
    plugin("build").buildStart.call(context);
    expect(emitted).toEqual(
      PUBLISHED.map((name) => ({
        type: "chunk",
        id: `\0published:${name}`,
        name: chunkName(name),
        preserveSignature: "strict",
      })),
    );
  });

  it("resolves and loads a virtual id as a re-export of the package", () => {
    const p = plugin("build");
    expect(p.resolveId("\0published:vue")).toBe("\0published:vue");
    expect(p.resolveId("vue")).toBeUndefined();
    expect(p.load("\0published:vue")).toBe('export * from "vue";');
    expect(p.load("\0published:crm/lib")).toBe(
      'export * from "/bench/apps/crm/crm/frontend/lib/index.js";',
    );
    expect(p.load("vue")).toBeUndefined();
  });

  it("injects the dev map when serving, the built map and links when bundled, and nothing before the bundle exists", () => {
    const html = "<html></html>";
    expect(plugin("serve").transformIndexHtml.handler(html, {})).toEqual({
      html,
      tags: [importMapTag(devImports(PUBLISHED))],
    });
    expect(plugin("build").transformIndexHtml.handler(html, {})).toBe(html);
    const bundle = bundleWith(PUBLISHED, ["assets/published-x.css"]);
    const result = plugin("build").transformIndexHtml.handler(html, { bundle });
    expect(result.tags.map((tag: any) => tag.tag)).toEqual(["script", "link"]);
    expect(JSON.parse(result.tags[0].children).imports.vue).toBe(
      `${base}assets/published-vue-abc123.js`,
    );
  });

  it("injects the map ahead of the module script", () => {
    const tag = importMapTag({ vue: "/x.js" });
    expect(tag.attrs.type).toBe("importmap");
    expect(tag.injectTo).toBe("head-prepend");
    expect(JSON.parse(tag.children)).toEqual({ imports: { vue: "/x.js" } });
  });
});
