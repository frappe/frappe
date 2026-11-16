// The canvas acts' input keys are the keys the server's `CANVAS_ACTS` reads for each edit.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import canvas from "../text/canvas";

const source = readFileSync(resolve(__dirname, "../../../../frappe/desk/doctype_editor/design_edits.py"), "utf8");
const placeKeys = [...source.match(/^PLACE_KEYS = \(([^)]*)\)/m)![1].matchAll(/"(\w+)"/g)].map((match) => match[1]);

function serverKeys(): Record<string, string[]> {
  const table = source.match(/^CANVAS_ACTS = \{([\s\S]*?)^\}/m)![1];
  const keys: Record<string, string[]> = {};
  for (const [, act, tail] of table.matchAll(/"canvas\.(\w+)": \(\s*"\w+",\s*(\([^)]*\)|PLACE_KEYS)/g))
    keys[act] = tail === "PLACE_KEYS" ? placeKeys : [...tail.matchAll(/"(\w+)"/g)].map((match) => match[1]);
  return keys;
}

describe("canvas acts", () => {
  it("take the keys the server reads", () => {
    const server = serverKeys();
    expect(Object.keys(server).length).toBe(13);
    for (const [act, keys] of Object.entries(server))
      expect(Object.keys((canvas[act as keyof typeof canvas].input as any).properties).sort(), act).toEqual([...keys].sort());
  });
});
