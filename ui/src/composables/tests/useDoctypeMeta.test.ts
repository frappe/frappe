import { beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";

// Hoisted so the factory passed to `vi.mock` can reference it.
const { getMeta } = vi.hoisted(() => ({ getMeta: vi.fn() }));

vi.mock("../../api", () => ({ getMeta }));

getMeta.mockImplementation(async (doctype: string) => ({
  data: { name: doctype, fields: [] },
  children: [{ name: `${doctype} Item`, fields: [] }],
}));

import { holdFresh } from "../../utils/sharedState";
import { markDoctypeMetaStale, resetDoctypeMeta, useDoctypeMeta } from "../useDoctypeMeta";
import type { DoctypeMeta } from "../useDoctypeMeta";

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

  it("fetches again after a mark, while a handle taken before keeps the meta it read", async () => {
    getMeta.mockResolvedValueOnce({ data: { name: "Note", fields: [{ fieldname: "old" }] } });
    const before = useDoctypeMeta("Note");
    await settled();

    markDoctypeMetaStale("Note");
    const after = useDoctypeMeta("Note");
    await settled();

    expect(getMeta).toHaveBeenCalledTimes(2);
    expect(before.meta.value?.fields).toEqual([{ fieldname: "old" }]);
    expect(after.meta.value?.fields).toEqual([]);
  });

  it("shows a later caller the stale meta at once, then the fresh one", async () => {
    getMeta.mockResolvedValueOnce({ data: { name: "Note", fields: [{ fieldname: "old" }] } });
    useDoctypeMeta("Note");
    await settled();

    markDoctypeMetaStale("Note");
    const fresh = deferred<{ data: DoctypeMeta }>();
    getMeta.mockReturnValueOnce(fresh.promise);
    const after = useDoctypeMeta("Note");

    expect(after.meta.value?.fields).toEqual([{ fieldname: "old" }]);
    expect(after.loading.value).toBe(false);
    expect(after.refreshing.value).toBe(true);

    fresh.resolve({ data: { name: "Note", fields: [{ fieldname: "new" }] } });
    await after.refreshed();

    expect(after.meta.value?.fields).toEqual([{ fieldname: "new" }]);
    expect(after.refreshing.value).toBe(false);
  });

  it("holds the fresh meta back until the hold is released, and resolves refreshed on arrival", async () => {
    getMeta.mockResolvedValueOnce({ data: { name: "Note", fields: [{ fieldname: "old" }] } });
    useDoctypeMeta("Note");
    await settled();

    markDoctypeMetaStale("Note");
    const release = holdFresh();
    getMeta.mockResolvedValueOnce({ data: { name: "Note", fields: [{ fieldname: "new" }] } });
    const after = useDoctypeMeta("Note");
    await after.refreshed();

    expect(after.meta.value?.fields).toEqual([{ fieldname: "old" }]);
    expect(after.refreshing.value).toBe(true);

    release();

    expect(after.meta.value?.fields).toEqual([{ fieldname: "new" }]);
    expect(after.refreshing.value).toBe(false);
  });

  it("resolves refreshed at once on an entry that is not a refresh", async () => {
    const { refreshed } = useDoctypeMeta("Note");
    let done = false;
    refreshed().then(() => (done = true));
    await Promise.resolve();

    expect(done).toBe(true);
  });

  it("keeps the stale meta without an error when the fresh read fails", async () => {
    getMeta.mockResolvedValueOnce({ data: { name: "Note", fields: [{ fieldname: "old" }] } });
    useDoctypeMeta("Note");
    await settled();

    markDoctypeMetaStale("Note");
    getMeta.mockRejectedValueOnce(new Error("Network down"));
    const after = useDoctypeMeta("Note");
    await after.refreshed();

    expect(after.meta.value?.fields).toEqual([{ fieldname: "old" }]);
    expect(after.error.value).toBeNull();
    expect(after.refreshError.value).toEqual(new Error("Network down"));
    expect(after.loading.value).toBe(false);
    expect(after.refreshing.value).toBe(false);
  });

  it("reads again for the next caller after a failed fresh read", async () => {
    getMeta.mockResolvedValueOnce({ data: { name: "Note", fields: [{ fieldname: "old" }] } });
    useDoctypeMeta("Note");
    await settled();
    markDoctypeMetaStale("Note");
    getMeta.mockRejectedValueOnce(new Error("Network down"));
    await useDoctypeMeta("Note").refreshed();

    getMeta.mockResolvedValueOnce({ data: { name: "Note", fields: [{ fieldname: "new" }] } });
    const next = useDoctypeMeta("Note");
    expect(next.meta.value?.fields).toEqual([{ fieldname: "old" }]);
    await next.refreshed();

    expect(getMeta).toHaveBeenCalledTimes(3);
    expect(next.meta.value?.fields).toEqual([{ fieldname: "new" }]);
  });

  it("resolves refreshed with the answer of a reload made during the refresh", async () => {
    getMeta.mockResolvedValueOnce({ data: { name: "Note", fields: [{ fieldname: "old" }] } });
    useDoctypeMeta("Note");
    await settled();
    markDoctypeMetaStale("Note");
    let answerFirst!: () => void;
    getMeta.mockImplementationOnce(
      () => new Promise((resolve) => (answerFirst = () => resolve({ data: { name: "Note", fields: [] } })))
    );
    getMeta.mockResolvedValueOnce({ data: { name: "Note", fields: [{ fieldname: "new" }] } });
    const after = useDoctypeMeta("Note");
    after.reload();
    await after.refreshed();

    expect(after.meta.value?.fields).toEqual([{ fieldname: "new" }]);
    answerFirst();
  });

  it("marks a parent's meta stale with its child table's, and leaves the rest", async () => {
    useDoctypeMeta("Note");
    useDoctypeMeta("Task");
    await settled();

    markDoctypeMetaStale("Note Item");
    const note = useDoctypeMeta("Note");
    useDoctypeMeta("Task");

    expect(getMeta.mock.calls.map(([doctype]) => doctype)).toEqual(["Note", "Task", "Note"]);
    expect(Object.keys(note.metas.value)).toEqual(["Note", "Note Item"]);
    expect(note.refreshing.value).toBe(true);
  });

  it("marks a meta still in flight stale, whose child tables are not known yet", async () => {
    useDoctypeMeta("Task");
    await settled();
    useDoctypeMeta("Note");

    markDoctypeMetaStale("Note Item");
    const note = useDoctypeMeta("Note");
    useDoctypeMeta("Task");

    expect(getMeta.mock.calls.map(([doctype]) => doctype)).toEqual(["Task", "Note", "Note"]);
    expect(note.loading.value).toBe(true);
    expect(note.refreshing.value).toBe(false);
  });

  it("marks a meta still refreshing stale, and seeds the next one with the same stale meta", async () => {
    getMeta.mockResolvedValueOnce({ data: { name: "Note", fields: [{ fieldname: "old" }] } });
    useDoctypeMeta("Note");
    await settled();
    markDoctypeMetaStale("Note");
    getMeta.mockReturnValueOnce(deferred().promise);
    useDoctypeMeta("Note");

    markDoctypeMetaStale("Task");
    const note = useDoctypeMeta("Note");

    expect(getMeta).toHaveBeenCalledTimes(3);
    expect(note.meta.value?.fields).toEqual([{ fieldname: "old" }]);
    expect(note.refreshing.value).toBe(true);
  });
});

function deferred<Value = unknown>() {
  let resolve!: (value: Value) => void;
  const promise = new Promise<Value>((done) => (resolve = done));
  return { promise, resolve };
}
