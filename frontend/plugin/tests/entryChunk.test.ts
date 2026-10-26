import { describe, expect, it } from "vitest";
import entryChunk, { shellChunkName } from "../entryChunk.js";

const ENTRY = "/f/src/main.ts";

const modules: Record<string, { isEntry: boolean }> = {
  "/f/index.html": { isEntry: true },
  [ENTRY]: { isEntry: false },
  "/f/node_modules/frappe-ui/src/components/Dialog.vue": { isEntry: false },
};
const context = { getModuleInfo: (id: string) => modules[id] ?? null };

describe("entryChunk", () => {
  it("groups every initial module in one chunk", () => {
    const config = (entryChunk(ENTRY) as any).config();
    const [group] = config.build.rolldownOptions.output.codeSplitting.groups;
    expect(group.tags).toEqual(["$initial"]);
    expect(
      group.name(
        "/f/node_modules/frappe-ui/src/components/Dialog.vue",
        context,
      ),
    ).toBe("shell");
  });

  it("leaves the entry modules in the entry chunk, so index.html keeps its chunk", () => {
    const name = shellChunkName(ENTRY);
    expect(name("/f/index.html", context)).toBeNull();
    expect(name(ENTRY, context)).toBeNull();
  });
});
