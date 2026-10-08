// @vitest-environment node
import { fileURLToPath } from "node:url";
import { build, type Rolldown } from "vite";
import { describe, expect, it } from "vitest";
import runtimeVue from "../runtimeVue.js";

const frontend = fileURLToPath(new URL("../..", import.meta.url));
// A call, not the definition the runtime build keeps on its export list.
const COMPILER_CALL = /(?<!function )registerRuntimeCompiler\(/;

// vuedraggable ships only UMD and CommonJS, so its `require("vue")` is the case to cover.
async function buildDraggable(alias: object[]) {
  const entry = {
    name: "entry",
    resolveId: (id: string) => (id === "entry" ? "\0entry" : undefined),
    load: (id: string) =>
      id === "\0entry"
        ? 'import draggable from "vuedraggable"; export default draggable;'
        : undefined,
  };
  const output = (await build({
    configFile: false,
    root: frontend,
    logLevel: "silent",
    plugins: [entry],
    resolve: { alias, preserveSymlinks: true },
    // Unminified, so the call keeps its name.
    build: { write: false, minify: false, rolldownOptions: { input: "entry" } },
  })) as Rolldown.RolldownOutput;
  return output.output.flatMap((file) => (file.type === "chunk" ? [file.code] : []));
}

describe("the vue every importer gets", () => {
  it("holds no template compiler, even for a CommonJS package", async () => {
    const chunks = await buildDraggable([runtimeVue]);
    expect(chunks.join("\n")).toContain("vuedraggable");
    for (const code of chunks) expect(code).not.toMatch(COMPILER_CALL);
  });

  it("would hold one without the alias, so the check above can fail", async () => {
    const chunks = await buildDraggable([]);
    expect(chunks.some((code) => COMPILER_CALL.test(code))).toBe(true);
  });
});
