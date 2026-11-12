// A doctype's list.js files load once, on its first list page, in run order: the owning app's, then each custom one.
// Its List Page Client Scripts follow them, from the same loader.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { call, evaluateClientScript } = vi.hoisted(() => ({ call: vi.fn(), evaluateClientScript: vi.fn() }));

vi.mock("frappe-ui", () => ({ toast: { success: vi.fn(), error: vi.fn() }, dialog: vi.fn() }));
vi.mock("@framework/ui/api", () => ({ runMethod: call }));
vi.mock("@/recordPage/evaluateClientScript", () => ({ evaluateClientScript }));

import { addListScript } from "@/contributions/registry";
import { invalidateClientScripts, resetClientScripts, watchClientScripts } from "@/recordPage/clientScripts";
import { LIST_PAGE_TIER } from "@/recordPage/clientScriptTypes";
import { listScriptsLoaded, listScriptsOf, loadListScripts } from "../scriptLoader";

let doctype = "";
let count = 0;

beforeEach(() => {
  resetClientScripts();
  call.mockReset();
  call.mockResolvedValue({ data: { scripts: [], can_write: false } });
  evaluateClientScript.mockReset();
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

  describe("List Page Client Scripts", () => {
    const rows = (...names: string[]) =>
      call.mockResolvedValue({ data: { scripts: names.map((name) => ({ name, script: name })), can_write: false } });
    const sourcesOf = () => listScriptsOf(doctype).map((one) => one.source);

    it("asks for the List Page view of the doctype, once, beside the files", async () => {
      rows();
      await Promise.all([loadListScripts(doctype), loadListScripts(doctype)]);
      expect(call).toHaveBeenCalledTimes(1);
      expect(call.mock.calls[0][1]).toEqual({ dt: doctype, view: "List Page" });
    });

    it("runs a stored script after the files, with the handlers list.js would give", async () => {
      const onRefresh = () => {};
      addListScript(doctype, { app: "crm", load: script({ onRefresh: () => {} }) });
      rows("late-script");
      evaluateClientScript.mockResolvedValue({ onRefresh, label: "ignored" });

      await loadListScripts(doctype);
      expect(sourcesOf()).toEqual(["crm", "client-script:late-script"]);
      const stored = listScriptsOf(doctype)[1];
      expect(stored.handlers).toEqual({ onRefresh });
    });

    it("is loaded only once the tier has registered", async () => {
      rows();
      expect(listScriptsLoaded(doctype)).toBe(false);
      await loadListScripts(doctype);
      expect(listScriptsLoaded(doctype)).toBe(true);
    });

    it("is not loaded while a save that landed with no list open waits to be read", async () => {
      evaluateClientScript.mockResolvedValue({ onRefresh: () => {} });
      rows("one");
      await loadListScripts(doctype);
      invalidateClientScripts(doctype, LIST_PAGE_TIER);
      expect(listScriptsLoaded(doctype)).toBe(false);
      rows("two");
      await loadListScripts(doctype);
      expect(listScriptsLoaded(doctype)).toBe(true);
      expect(sourcesOf()).toEqual(["client-script:two"]);
    });

    it("reads the tier again on the next load after a failed first fetch", async () => {
      evaluateClientScript.mockResolvedValue({ onRefresh: () => {} });
      call.mockRejectedValueOnce(new Error("offline"));
      await loadListScripts(doctype);
      expect(listScriptsLoaded(doctype)).toBe(false);
      rows("one");
      await loadListScripts(doctype);
      expect(listScriptsLoaded(doctype)).toBe(true);
      expect(sourcesOf()).toEqual(["client-script:one"]);
    });

    it("swaps the tier when a script changes on the server, leaving the files", async () => {
      const socket = { handlers: new Map<string, (...args: unknown[]) => void>() } as any;
      socket.on = (name: string, handler: (...args: unknown[]) => void) => socket.handlers.set(name, handler);
      socket.off = () => {};
      watchClientScripts(socket);
      addListScript(doctype, { app: "crm", load: script({ onRefresh: () => {} }) });
      evaluateClientScript.mockResolvedValue({ onRefresh: () => {} });
      rows("first");
      await loadListScripts(doctype);

      rows("second");
      socket.handlers.get("client_script_changed")({ dt: doctype, view: "List Page", page: null });
      await loadListScripts(doctype);
      expect(sourcesOf()).toEqual(["crm", "client-script:second"]);
    });

    it("ignores a change to the record page's scripts", async () => {
      rows("first");
      evaluateClientScript.mockResolvedValue({});
      await loadListScripts(doctype);
      invalidateClientScripts(doctype);
      await loadListScripts(doctype);
      expect(call).toHaveBeenCalledTimes(1);
      invalidateClientScripts(doctype, LIST_PAGE_TIER);
      await loadListScripts(doctype);
      expect(call).toHaveBeenCalledTimes(2);
    });

    it("skips a script that fails to evaluate and keeps the rest", async () => {
      rows("broken", "fine");
      evaluateClientScript.mockRejectedValueOnce(new Error("syntax")).mockResolvedValue({ onRefresh: () => {} });
      await loadListScripts(doctype);
      expect(sourcesOf()).toEqual(["client-script:fine"]);
    });
  });
});
