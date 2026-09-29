import { gzipSync } from "node:zlib";
import { describe, expect, it } from "vitest";
import { jsSizeProblems, pageJsKb } from "../check-page-js.mjs";

const manifest = {
  "index.html": { file: "assets/index.js", imports: ["_vue.js"] },
  "_vue.js": { file: "assets/vue.js" },
  "_shared.js": { file: "assets/shared.js", imports: ["_vue.js"] },
  "src/pages/Home.vue": { file: "assets/Home.js" },
  "src/pages/List.vue": { file: "assets/List.js", imports: ["_shared.js"] },
  "src/pages/Record.vue": {
    file: "assets/Record.js",
    imports: ["_shared.js", "_vue.js"],
    dynamicImports: ["_editor.js"],
  },
  "_editor.js": { file: "assets/editor.js" },
};

const kb = (bytes: number) => Math.round((bytes / 1024) * 10) / 10;
const gzipped = (file: string) => gzipSync(Buffer.from(file.repeat(2000))).length;

describe("pageJsKb", () => {
  it("adds the gzip size of the entry, the page and what each imports statically, once each", () => {
    const read = (file: string) => Buffer.from(file.repeat(2000));
    const entry = gzipped("assets/index.js") + gzipped("assets/vue.js");

    expect(pageJsKb(manifest, read)).toEqual({
      home: kb(entry + gzipped("assets/Home.js")),
      list: kb(entry + gzipped("assets/List.js") + gzipped("assets/shared.js")),
      record: kb(entry + gzipped("assets/Record.js") + gzipped("assets/shared.js")),
    });
  });

  it("names a page chunk that the build no longer has", () => {
    const { "src/pages/List.vue": _, ...withoutList } = manifest;

    expect(() => pageJsKb(withoutList, () => Buffer.from(""))).toThrow(
      "src/pages/List.vue is not a chunk in the build manifest"
    );
  });
});

describe("jsSizeProblems", () => {
  const budgets = {
    jsToleranceKb: 5,
    home: { baseline: { jsKb: 100 } },
    list: { baseline: { jsKb: 200 } },
  };

  it("passes a page up to the tolerance above its baseline, and any page below it", () => {
    expect(jsSizeProblems({ home: 105, list: 150 }, budgets)).toEqual([]);
  });

  it("fails a page more than the tolerance above its baseline and names the new value", () => {
    expect(jsSizeProblems({ home: 105.1, list: 200 }, budgets)).toEqual([
      expect.stringMatching(/^home: 105.1 KB .* above its baseline of 100 KB\. .* to 105\.1\.$/),
    ]);
  });
});
