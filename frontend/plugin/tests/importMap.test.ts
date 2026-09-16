import { describe, expect, it } from "vitest";
import importMap, {
  PUBLISHED,
  builtImports,
  chunkName,
  devImports,
  importMapTag,
  publishedChunks,
  stylesheetTags,
} from "../importMap.js";

const base = "/assets/frappe/frontend/";

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

function plugin(command: "build" | "serve") {
  const p = importMap() as any;
  p.configResolved({ base, command });
  return p;
}

describe("the published import map", () => {
  it("names what a stored script may import, and nothing the build merely enforces", () => {
    expect(PUBLISHED).toEqual([
      "vue",
      "vue-router",
      "frappe-ui",
      "@framework/ui",
    ]);
  });

  it("points each name at its emitted chunk under the build's base", () => {
    expect(builtImports(publishedChunks(bundleWith(PUBLISHED)), base)).toEqual({
      vue: `${base}assets/published-vue-abc123.js`,
      "vue-router": `${base}assets/published-vue-router-abc123.js`,
      "frappe-ui": `${base}assets/published-frappe-ui-abc123.js`,
      "@framework/ui": `${base}assets/published-framework-ui-abc123.js`,
    });
  });

  it("spells a scoped name without its punctuation", () => {
    expect(chunkName("@framework/ui")).toBe("published-framework-ui");
  });

  it("fails the build when a name has no chunk, so the page never ships a map with a hole", () => {
    expect(() => publishedChunks(bundleWith(["vue", "frappe-ui"]))).toThrow(
      "no entry chunk emitted for vue-router",
    );
  });

  it("links a published chunk's stylesheet once, so a script-imported component is styled", () => {
    const bundle = bundleWith(PUBLISHED, ["assets/published-x.css"]);
    expect(stylesheetTags(publishedChunks(bundle), bundle, base)).toEqual([
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
    expect(stylesheetTags(publishedChunks(bare), bare, base)).toEqual([]);
  });

  it("links the stylesheets of the chunks a published chunk imports, through a cycle", () => {
    const bundle = withSharedChunk(
      bundleWith(PUBLISHED, [], ["assets/shared-1.js"]),
      "assets/shared.css",
    );
    const hrefs = stylesheetTags(publishedChunks(bundle), bundle, base).map(
      (tag) => tag.attrs.href,
    );
    expect(hrefs).toEqual([`${base}assets/shared.css`]);
  });

  it("skips a stylesheet the document already links", () => {
    const bundle = bundleWith(PUBLISHED, ["assets/published-x.css"]);
    const html = `<link rel="stylesheet" href="${base}assets/published-x.css">`;
    expect(stylesheetTags(publishedChunks(bundle), bundle, base, html)).toEqual(
      [],
    );
  });

  it("serves the dev map from stable virtual ids", () => {
    expect(devImports().vue).toBe("/@id/__x00__published:vue");
  });

  it("takes the list as an input, so a build can publish more than the framework's names", () => {
    const emitted: any[] = [];
    const p = importMap(["vue", "myapp"]) as any;
    p.configResolved({ base, command: "build" });
    p.buildStart.call({ emitFile: (file: unknown) => emitted.push(file) });
    expect(emitted.map((file) => file.name)).toEqual([
      "published-vue",
      "published-myapp",
    ]);
    expect(Object.keys(devImports(["vue", "myapp"]))).toEqual(["vue", "myapp"]);
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
    expect(p.load("vue")).toBeUndefined();
  });

  it("injects the dev map when serving, the built map and links when bundled, and nothing before the bundle exists", () => {
    const html = "<html></html>";
    expect(plugin("serve").transformIndexHtml.handler(html, {})).toEqual({
      html,
      tags: [importMapTag(devImports())],
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
