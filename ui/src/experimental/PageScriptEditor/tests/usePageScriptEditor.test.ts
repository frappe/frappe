// The Page Script editor's state (wayfinder ticket 16) as executable claims.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick, ref } from "vue";

const { list, create, save, remove } = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  save: vi.fn(),
  remove: vi.fn(),
}));

vi.mock("../pageScriptApi", () => ({
  pageScriptApi: { list, create, save, remove },
}));

import { usePageScriptEditor } from "../usePageScriptEditor";

function rows(...names: string[]) {
  return names.map((name, index) => ({
    name,
    dt: "CRM Deal",
    view: "Record",
    enabled: 1 as const,
    module: null,
    script: `// ${name}`,
    run_order: index + 1,
    modified: `2026-08-13 00:00:0${index}`,
  }));
}

/** Runs the composable's initial load, which its `immediate` watch kicks off. */
async function editorFor(doctype = ref("CRM Deal")) {
  const editor = usePageScriptEditor(doctype);
  await vi.waitFor(() => expect(editor.loading.value).toBe(false));
  return editor;
}

describe("the script a host addresses", () => {
  beforeEach(() => {
    list.mockReset();
    list.mockResolvedValue(rows("oldest", "newest"));
  });

  it("opens the bound script rather than the last one", async () => {
    const bound = ref<string | undefined>("oldest");
    const editor = usePageScriptEditor(ref("CRM Deal"), bound);
    await vi.waitFor(() => expect(editor.loading.value).toBe(false));

    expect(editor.selectedName.value).toBe("oldest");
  });

  it("corrects a name no script answers to, so a deleted link still opens", async () => {
    const bound = ref<string | undefined>("deleted");
    const editor = usePageScriptEditor(ref("CRM Deal"), bound);
    await vi.waitFor(() => expect(editor.loading.value).toBe(false));

    expect(editor.selectedName.value).toBe("newest");
  });

  it("follows the bound name when the host changes it", async () => {
    const bound = ref<string | undefined>("newest");
    const editor = usePageScriptEditor(ref("CRM Deal"), bound);
    await vi.waitFor(() => expect(editor.loading.value).toBe(false));

    bound.value = "oldest";
    await nextTick();

    expect(editor.selectedName.value).toBe("oldest");
  });

  it("falls back when the host changes it to a name no script answers to", async () => {
    const bound = ref<string | undefined>("oldest");
    const editor = usePageScriptEditor(ref("CRM Deal"), bound);
    await vi.waitFor(() => expect(editor.loading.value).toBe(false));

    bound.value = "deleted";
    await nextTick();

    expect(editor.selectedName.value).toBe("newest");
  });

  it("leaves the selection alone when nothing is bound", async () => {
    const editor = usePageScriptEditor(ref("CRM Deal"), ref(undefined));
    await vi.waitFor(() => expect(editor.loading.value).toBe(false));

    expect(editor.selectedName.value).toBe("newest");
  });
});

describe("the Page Script editor", () => {
  beforeEach(() => {
    list.mockReset();
    create.mockReset();
    save.mockReset();
    remove.mockReset();
    list.mockResolvedValue(rows("oldest", "newest"));
  });

  it("lists the doctype's scripts in run order and opens the last one", async () => {
    const editor = await editorFor();

    expect(editor.scripts.value.map((row) => row.name)).toEqual([
      "oldest",
      "newest",
    ]);
    // Creation order is run order, so the last row is the one that wins.
    expect(editor.selectedName.value).toBe("newest");
    expect(editor.draft.value).toBe("// newest");
  });

  it("reports the buffer dirty only once it differs from the saved script", async () => {
    const editor = await editorFor();
    expect(editor.dirty.value).toBe(false);

    editor.draft.value = "// edited";
    expect(editor.dirty.value).toBe(true);
  });

  it("keeps one buffer per script, so switching loses no edit", async () => {
    const editor = await editorFor();
    editor.draft.value = "// edited newest";

    editor.select("oldest");
    expect(editor.draft.value).toBe("// oldest");
    expect(editor.dirty.value).toBe(false);

    editor.select("newest");
    expect(editor.draft.value).toBe("// edited newest");
    expect(editor.dirty.value).toBe(true);
  });

  it("does not lose an unsaved edit to the reload another write triggers", async () => {
    const editor = await editorFor();
    editor.select("newest");
    editor.draft.value = "// still typing";

    await editor.setEnabled(editor.scripts.value[0], false);

    expect(editor.draft.value).toBe("// still typing");
    expect(editor.dirty.value).toBe(true);
  });

  it("sends the whole document, so a save cannot blank a field it left out", async () => {
    const editor = await editorFor();
    editor.draft.value = "// edited";

    await editor.save();

    expect(save).toHaveBeenCalledWith({
      ...rows("oldest", "newest")[1],
      script: "// edited",
    });
  });

  it("clears the buffer once its script is saved", async () => {
    const editor = await editorFor();
    editor.draft.value = "// edited";
    list.mockResolvedValue([
      rows("oldest", "newest")[0],
      { ...rows("oldest", "newest")[1], script: "// edited" },
    ]);

    await editor.save();

    expect(editor.dirty.value).toBe(false);
  });

  it("does not call the server for a save with nothing to save", async () => {
    const editor = await editorFor();
    await editor.save();
    expect(save).not.toHaveBeenCalled();
  });

  it("opens a newly created script", async () => {
    const editor = await editorFor();
    create.mockResolvedValue({ name: "third" });
    list.mockResolvedValue(rows("oldest", "newest", "third"));

    await editor.create("third");

    // run_order 3: last, behind the two positioned scripts already loaded.
    expect(create).toHaveBeenCalledWith({
      name: "third",
      dt: "CRM Deal",
      run_order: 3,
    });
    expect(editor.selectedName.value).toBe("third");
  });

  // Ticket 28: without the seed a new script takes the doctype default of 0 and
  // sorts ahead of every positioned script — the opposite of "the newest wins".
  it("seeds a new script last even when every script is still unpositioned", async () => {
    list.mockResolvedValue(
      rows("oldest", "newest").map((row) => ({ ...row, run_order: 0 })),
    );
    const editor = await editorFor();
    create.mockResolvedValue({ name: "third" });

    await editor.create("third");

    expect(create.mock.calls[0][0].run_order).toBe(1);
  });

  // Ticket 26: Duplicate arrived with the row's `⋯` menu.
  it("duplicates a script disabled, so the copy cannot run beside its original", async () => {
    const editor = await editorFor();
    create.mockResolvedValue({ name: "oldest-copy" });
    list.mockResolvedValue(rows("oldest", "newest", "oldest-copy"));

    await editor.duplicate(editor.scripts.value[0]);

    expect(create).toHaveBeenCalledWith({
      name: "oldest-copy",
      dt: "CRM Deal",
      view: "Record",
      script: "// oldest",
      enabled: 0,
      run_order: 3,
    });
    expect(editor.selectedName.value).toBe("oldest-copy");
  });

  it("duplicates the buffer, not the saved text — you copy what you are looking at", async () => {
    const editor = await editorFor();
    editor.select("oldest");
    editor.draft.value = "// edited, not saved";
    create.mockResolvedValue({ name: "oldest-copy" });

    await editor.duplicate(editor.scripts.value[0]);

    expect(create.mock.calls[0][0].script).toBe("// edited, not saved");
  });

  it("steps the copy's suffix past a name already taken", async () => {
    const editor = await editorFor(ref("CRM Deal"));
    list.mockResolvedValue(rows("oldest", "newest", "oldest-copy"));
    await editor.load();
    create.mockResolvedValue({ name: "oldest-copy-2" });

    await editor.duplicate(editor.scripts.value[0]);

    expect(create.mock.calls[0][0].name).toBe("oldest-copy-2");
  });

  it("writes the enabled flag as the doctype's 0/1", async () => {
    const editor = await editorFor();
    await editor.setEnabled(editor.scripts.value[0], false);
    expect(save).toHaveBeenCalledWith({ ...rows("oldest")[0], enabled: 0 });
  });

  it("re-opens the last surviving script after a delete", async () => {
    const editor = await editorFor();
    list.mockResolvedValue(rows("oldest"));

    await editor.remove(editor.scripts.value[1]);

    expect(remove).toHaveBeenCalledWith("newest");
    expect(editor.selectedName.value).toBe("oldest");
  });

  it("keeps the selection when a delete fails", async () => {
    const editor = await editorFor();
    remove.mockRejectedValue(new Error("nope"));

    await editor.remove(editor.scripts.value[1]);

    expect(editor.selectedName.value).toBe("newest");
    expect(editor.error.value).toBe("nope");
  });

  it("reports a failed save without rejecting into its caller", async () => {
    const editor = await editorFor();
    editor.draft.value = "// edited";
    save.mockRejectedValue(new Error("Document has been modified"));

    await expect(editor.save()).resolves.toBeUndefined();
    expect(editor.error.value).toBe("Document has been modified");
    // The edit survives the failure — it is the only copy of it.
    expect(editor.draft.value).toBe("// edited");
  });

  it("lets a failed create reject, so the naming dialog can stay open", async () => {
    const editor = await editorFor();
    create.mockRejectedValue(new Error("already exists"));

    await expect(editor.create("dupe")).rejects.toThrow("already exists");
  });

  it("surfaces a failed load instead of throwing", async () => {
    list.mockRejectedValue(new Error("not permitted"));
    const editor = await editorFor();

    expect(editor.error.value).toBe("not permitted");
    expect(editor.scripts.value).toEqual([]);
  });

  it("reloads when the doctype changes", async () => {
    const doctype = ref("CRM Deal");
    const editor = await editorFor(doctype);

    list.mockResolvedValue(rows("lead-script"));
    doctype.value = "CRM Lead";
    await nextTick();
    await vi.waitFor(() => expect(editor.loading.value).toBe(false));

    expect(editor.scripts.value.map((row) => row.name)).toEqual([
      "lead-script",
    ]);
    expect(editor.selectedName.value).toBe("lead-script");
  });

  it("lets the later of two overlapping loads win", async () => {
    const editor = await editorFor();

    let releaseStale: (rows: unknown) => void = () => {};
    list.mockReturnValueOnce(
      new Promise((resolve) => (releaseStale = resolve)),
    );
    const slow = editor.load();

    list.mockResolvedValue(rows("fresh"));
    await editor.load();
    releaseStale(rows("stale"));
    await slow;

    expect(editor.scripts.value.map((row) => row.name)).toEqual(["fresh"]);
    expect(editor.loading.value).toBe(false);
  });
});
