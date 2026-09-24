import { beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";

// Hoisted so the factory passed to `vi.mock` can reference it.
const { getMeta } = vi.hoisted(() => ({ getMeta: vi.fn() }));

vi.mock("../../api", () => ({ getMeta }));

getMeta.mockImplementation(async (doctype: string) => ({
  data: { name: doctype, fields: [] },
  children: [{ name: `${doctype} Item`, fields: [] }],
}));

import { dropDoctypeMeta, resetDoctypeMeta, useDoctypeMeta } from "../useDoctypeMeta";

const settled = () => new Promise((resolve) => setTimeout(resolve, 0));

describe("useDoctypeMeta", () => {
  beforeEach(() => {
    resetDoctypeMeta();
    vi.clearAllMocks();
  });

  it("fetches a doctype's meta with its children once, however many callers ask", async () => {
    useDoctypeMeta("Note");
    useDoctypeMeta("Note");

    expect(getMeta).toHaveBeenCalledTimes(1);
    expect(getMeta).toHaveBeenCalledWith("Note", { include: ["children"] });
  });

  it("reads the meta of the doctype it was asked for, and keys the children beside it", async () => {
    const { meta, metas, loading } = useDoctypeMeta("Note");
    expect(loading.value).toBe(true);
    await settled();

    expect(loading.value).toBe(false);
    expect(meta.value?.name).toBe("Note");
    expect(Object.keys(metas.value)).toEqual(["Note", "Note Item"]);
  });

  it("follows a reactive doctype onto the other meta", async () => {
    const doctype = ref("Note");
    const { meta } = useDoctypeMeta(doctype);
    await settled();

    expect(meta.value?.name).toBe("Note");

    doctype.value = "Task";
    // The entry is built on the first read after the move; nothing fetches before it.
    expect(meta.value).toBeNull();
    await settled();

    expect(meta.value?.name).toBe("Task");
    expect(getMeta).toHaveBeenCalledTimes(2);
  });

  it("goes back to a meta it already holds rather than refetching it", async () => {
    const doctype = ref("Note");
    const { meta } = useDoctypeMeta(doctype);

    doctype.value = "Task";
    expect(meta.value).toBeNull();
    await settled();
    expect(meta.value?.name).toBe("Task");
    doctype.value = "Note";

    expect(meta.value?.name).toBe("Note");
    expect(getMeta).toHaveBeenCalledTimes(2);
  });

  it("holds the error of a failed read, and clears it on a reload that succeeds", async () => {
    getMeta.mockRejectedValueOnce(new Error("Not permitted"));
    const { meta, error, reload } = useDoctypeMeta("Note");
    await settled();

    expect(meta.value).toBeNull();
    expect(String(error.value)).toContain("Not permitted");

    reload();
    await settled();

    expect(error.value).toBeNull();
    expect(meta.value?.name).toBe("Note");
  });

  it("fetches again after a drop, while a handle taken before keeps the meta it read", async () => {
    getMeta.mockResolvedValueOnce({ data: { name: "Note", fields: [{ fieldname: "old" }] } });
    const before = useDoctypeMeta("Note");
    await settled();

    dropDoctypeMeta("Note");
    const after = useDoctypeMeta("Note");
    await settled();

    expect(getMeta).toHaveBeenCalledTimes(2);
    expect(before.meta.value?.fields).toEqual([{ fieldname: "old" }]);
    expect(after.meta.value?.fields).toEqual([]);
  });

  it("drops a parent's meta with its child table's, and leaves the rest", async () => {
    useDoctypeMeta("Note");
    useDoctypeMeta("Task");
    await settled();

    dropDoctypeMeta("Note Item");
    useDoctypeMeta("Note");
    useDoctypeMeta("Task");

    expect(getMeta.mock.calls.map(([doctype]) => doctype)).toEqual(["Note", "Task", "Note"]);
  });
});
