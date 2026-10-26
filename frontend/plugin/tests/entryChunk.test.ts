// @vitest-environment node
import { fileURLToPath } from "node:url";
import { build, type Plugin, type Rolldown } from "vite";
import { describe, expect, it } from "vitest";
import entryChunk from "../entryChunk.js";
import importMap from "../importMap.js";

const frontend = fileURLToPath(new URL("../..", import.meta.url));

// The entry and a lazy page share `shared`; a published package reaches `extra`, which no page uses.
const SOURCES: Record<string, string> = {
  "\0entry":
    'import { shared } from "\0shared"; console.log(shared, () => import("\0lazy"));',
  "\0shared": 'export const shared = "shared";',
  "\0lazy":
    'import { shared } from "\0shared"; import { own } from "\0own"; export default shared + own;',
  "\0own": 'export const own = "own";',
  "\0pkg":
    'import { shared } from "\0shared"; export { extra } from "\0extra"; export const pkg = shared;',
  "\0extra": 'export const extra = "extra";',
};
const graph = {
  name: "graph",
  resolveId: (id: string) =>
    id === "entry" ? "\0entry" : id === "pkg" ? "\0pkg" : SOURCES[id] && id,
  load: (id: string) => SOURCES[id],
};
const manifest = [
  { app: "frappe", source_dir: "/f", import_map: { pkg: "pkg" } },
];

async function chunks(plugins: Plugin[]) {
  const output = (await build({
    configFile: false,
    root: frontend,
    logLevel: "silent",
    plugins: [graph, importMap(manifest), ...plugins],
    build: { write: false, minify: false, rolldownOptions: { input: "entry" } },
  })) as Rolldown.RolldownOutput;
  return output.output.filter(
    (file) => file.type === "chunk",
  ) as Rolldown.OutputChunk[];
}

/** The modules the cold load runs: the entry chunk and every chunk it imports statically. */
function coldLoad(all: Rolldown.OutputChunk[]) {
  const loaded = new Map<string, Rolldown.OutputChunk>();
  const visit = (chunk: Rolldown.OutputChunk) => {
    if (loaded.has(chunk.fileName)) return;
    loaded.set(chunk.fileName, chunk);
    for (const file of chunk.imports)
      visit(all.find((c) => c.fileName === file)!);
  };
  visit(all.find((chunk) => chunk.facadeModuleId === "\0entry")!);
  return {
    files: loaded.size,
    modules: [...loaded.values()].flatMap((chunk) => chunk.moduleIds),
  };
}

describe("the entry chunk rule", () => {
  it("keeps a module the entry shares with a lazy chunk beside the entry, in one chunk", async () => {
    const all = await chunks([entryChunk("\0entry")]);
    const { files, modules } = coldLoad(all);
    expect(modules).toContain("\0shared");
    expect(modules).not.toContain("\0own");
    expect(modules).not.toContain("\0extra");
    expect(files).toBeLessThanOrEqual(2);
    expect(
      all.find((chunk) => chunk.facadeModuleId === "\0lazy")?.isDynamicEntry,
    ).toBe(true);
  });

  it("keeps every export of a published name, out of the cold load", async () => {
    const all = await chunks([entryChunk("\0entry")]);
    const published = all.find(
      (chunk) => chunk.facadeModuleId === "\0published:pkg",
    )!;
    expect(published.exports.sort()).toEqual(["extra", "pkg"]);
    expect(published.fileName).toMatch(/^assets\/published-pkg-/);
    expect(coldLoad(all).modules).not.toContain("\0published:pkg");
  });

  it("would split the shared module out without the rule, so the check above can fail", async () => {
    const { files, modules } = coldLoad(await chunks([]));
    expect(modules).toContain("\0shared");
    expect(files).toBeGreaterThan(2);
  });

  it("would pull a package into the cold load if a plugin emitted it as an entry", async () => {
    const emitsPkg = {
      name: "emits-pkg",
      buildStart(this: any) {
        this.emitFile({
          type: "chunk",
          id: "\0pkg",
          preserveSignature: "strict",
        });
      },
    };
    const { modules } = coldLoad(
      await chunks([entryChunk("\0entry"), emitsPkg]),
    );
    expect(modules).toContain("\0extra");
  });
});
