// A doctype's list.js files load once, on its first list page, in run order: the owning app's, then each custom one.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { addListScript } from "@/contributions/registry";
import { listScriptsLoaded, listScriptsOf, loadListScripts } from "../scriptLoader";

let doctype = "";
let count = 0;

beforeEach(() => {
  // The loader keeps its scripts for the session; each test takes a doctype of its own.
  doctype = `Loader Doctype ${++count}`;
  vi.spyOn(console, "error").mockImplementation(() => {});
  vi.spyOn(console, "warn").mockImplementation(() => {});
});

afterEach(() => vi.restoreAllMocks());

const script = (exported: Record<string, unknown>) => () => Promise.resolve({ default: exported });

describe("the list script loader", () => {
  it("runs the owning app's list.js before a custom one, whatever order they land in", async () => {
    let landOwner!: () => void;
    const ownerLanded = new Promise<void>((resolve) => (landOwner = resolve));
    addListScript(doctype, {
      app: "crm",
      load: () => ownerLanded.then(() => ({ default: { onRefresh: () => {} } })),
    });
    addListScript(doctype, { app: "custom", load: script({ onRefresh: () => {} }) });

    const loading = loadListScripts(doctype);
    expect(listScriptsLoaded(doctype)).toBe(false);
    landOwner();
    await loading;

    expect(listScriptsLoaded(doctype)).toBe(true);
    expect(listScriptsOf(doctype).map((one) => one.source)).toEqual(["crm", "custom"]);
  });

  it("fetches a doctype's files once, however many pages ask", async () => {
    const load = vi.fn(script({ onRefresh: () => {} }));
    addListScript(doctype, { app: "crm", load });

    await Promise.all([loadListScripts(doctype), loadListScripts(doctype)]);
    await loadListScripts(doctype);
    expect(load).toHaveBeenCalledTimes(1);
  });

  it("tries a failed fetch again on the next page", async () => {
    const load = vi
      .fn()
      .mockRejectedValueOnce(new Error("chunk failed"))
      .mockImplementation(script({ onRefresh: () => {} }));
    addListScript(doctype, { app: "crm", load });

    await loadListScripts(doctype);
    expect(listScriptsLoaded(doctype)).toBe(false);
    expect(listScriptsOf(doctype)).toEqual([]);

    await loadListScripts(doctype);
    expect(load).toHaveBeenCalledTimes(2);
    expect(listScriptsLoaded(doctype)).toBe(true);
    expect(listScriptsOf(doctype)).toHaveLength(1);
  });

  it("keeps function keys as handlers and drops the rest", async () => {
    const onRefresh = () => {};
    addListScript(doctype, { app: "crm", load: script({ onRefresh, columns: [], label: "Leads" }) });

    await loadListScripts(doctype);
    const [loaded] = listScriptsOf(doctype);
    expect(loaded.handlers).toEqual({ onRefresh });
  });

  it("skips a file with no default export", async () => {
    addListScript(doctype, { app: "crm", load: () => Promise.resolve({}) });
    await loadListScripts(doctype);
    expect(listScriptsLoaded(doctype)).toBe(true);
    expect(listScriptsOf(doctype)).toEqual([]);
  });

  it("answers at once for a doctype with no list.js", async () => {
    await loadListScripts(doctype);
    expect(listScriptsLoaded(doctype)).toBe(true);
  });
});
