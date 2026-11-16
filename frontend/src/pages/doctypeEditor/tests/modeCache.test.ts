import { describe, expect, it, vi } from "vitest";
import { ModeCache } from "../modeCache";
import { taskNote } from "./editorFixture";

function cache() {
  const load = vi.fn(async (doctype: string, mode = "Design" as const) =>
    taskNote({ doctype, mode }),
  );
  return { load, modes: new ModeCache(load) };
}

describe("the editor's mode cache", () => {
  it("loads a DocType's mode once", async () => {
    const { load, modes } = cache();
    await modes.get("ToDo", "Design");
    await modes.get("ToDo", "Design");
    expect(load).toHaveBeenCalledOnce();
  });

  it("holds the default mode under the mode the server picked", async () => {
    const { load, modes } = cache();
    await modes.get("ToDo");
    await modes.get("ToDo", "Design");
    expect(load).toHaveBeenCalledOnce();
  });

  it("hands out a copy, so edits never reach the cached load", async () => {
    const { modes } = cache();
    (await modes.get("ToDo", "Design")).definition.fields.pop();
    const again = await modes.get("ToDo", "Design");
    expect(again.definition.fields).toEqual(taskNote().definition.fields);
  });

  it("loads both modes again after a save", async () => {
    const { load, modes } = cache();
    await modes.get("ToDo", "Design");
    await modes.get("ToDo", "Customize");
    await modes.refresh("ToDo", "Design");
    await modes.get("ToDo", "Customize");
    expect(load).toHaveBeenCalledTimes(4);
  });

  it("holds one DocType at a time", async () => {
    const { load, modes } = cache();
    await modes.get("ToDo", "Design");
    await modes.get("Note", "Design");
    await modes.get("ToDo", "Design");
    expect(load).toHaveBeenCalledTimes(3);
  });

  it("does not keep a load that began before a save", async () => {
    const { load, modes } = cache();
    const slow = modes.get("ToDo", "Customize");
    await modes.refresh("ToDo", "Design");
    await slow;
    await modes.get("ToDo", "Customize");
    expect(load).toHaveBeenCalledTimes(3);
  });

  it("reuses the mode the server picked when none was asked for", async () => {
    const { load, modes } = cache();
    await modes.get("ToDo");
    await modes.get("ToDo", "Customize");
    await modes.get("ToDo");
    expect(load).toHaveBeenCalledTimes(2);
  });
});
