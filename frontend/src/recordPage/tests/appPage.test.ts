// An app page made with the builder runs its own app's handler file, then the Client Scripts that name it.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick, watchEffect } from "vue";

const { call, evaluateClientScript } = vi.hoisted(() => ({
  call: vi.fn(),
  evaluateClientScript: vi.fn(),
}));

vi.mock("frappe-ui", () => ({ toast: { success: vi.fn(), error: vi.fn() }, dialog: vi.fn() }));
vi.mock("@framework/ui/api", () => ({ runMethod: call }));
vi.mock("../evaluateClientScript", () => ({ evaluateClientScript }));

import { createPageEngine } from "@/pageEngine/createPageEngine";
import { setAppPageScripts } from "@/pageEngine/appPageScripts";
import { Surface } from "@/pageEngine/surface";
import { invalidateClientScripts, resetClientScripts } from "../clientScripts";
import { appPageScriptSource } from "../appPageScriptSource";
import { addPageFile, resetPageScripts } from "../pageScripts";

const DOCTYPE = "Widget Board";

type Script = Record<string, (page: any) => unknown>;

/** The stored scripts per page name, as the server would answer them. */
let stored: Record<string, Record<string, Script>>;
const built: { leave: () => void }[] = [];

function makeEngine(app = "acme", pageName = "board") {
  const widgets = new Surface({ surface: "widgets", keys: ["name", "label"] });
  widgets.provideBuiltins(() => [{ name: "a" }, { name: "b" }]);
  const engine = createPageEngine({
    doctype: DOCTYPE,
    name: "Board",
    pageName,
    app,
    lists: { widgets },
    extras: () => ({}),
    meta: () => null,
    perms: () => ({}),
    roles: () => [],
    router: { currentRoute: { value: { path: "/board" } } } as any,
  });
  built.push(engine);
  return engine;
}

const drawn = (engine: ReturnType<typeof makeEngine>) =>
  engine.lists.widgets.visible().map((one) => one.name);

beforeEach(() => {
  stored = {};
  call.mockClear();
  setAppPageScripts(appPageScriptSource);
  resetPageScripts();
  resetClientScripts();
  call.mockImplementation(async (_method: string, params: { page: string }) => ({
    data: {
      scripts: Object.keys(stored[params.page] ?? {}).map((name) => ({ name, script: "" })),
      can_write: false,
    },
  }));
  evaluateClientScript.mockImplementation(async (row: { name: string }) => {
    const scripts = Object.values(stored).find((page) => row.name in page)!;
    return scripts[row.name];
  });
});

afterEach(() => {
  // A page still on screen would re-run when the next test resets the change counts.
  for (const engine of built.splice(0)) engine.leave();
  setAppPageScripts(null);
  vi.restoreAllMocks();
});

describe("an app page", () => {
  it("paints its handler file and its Client Scripts as one end state", async () => {
    addPageFile("acme", DOCTYPE, "board", {
      onRefresh: (page: any) => page.widgets.add([{ name: "c" }]),
    });
    stored.board = { "hide-a": { onRefresh: (page) => page.widgets.hide("a") } };
    const engine = makeEngine();
    const paints: string[][] = [];
    watchEffect(() => paints.push(drawn(engine)));

    await engine.refresh();
    await nextTick();

    expect(drawn(engine)).toEqual(["b", "c"]);
    expect(paints).toEqual([["a", "b"], ["b", "c"]]);
    expect(call).toHaveBeenCalledWith(
      "frappe.custom.doctype.client_script.client_script.get_client_scripts",
      { dt: DOCTYPE, view: "App Page", page: "board" },
      { http: "GET" },
    );
  });

  it("runs no other app's handler file and no Client Script of another page", async () => {
    addPageFile("other", DOCTYPE, "board", {
      onRefresh: (page: any) => page.widgets.hide("a"),
    });
    stored.kanban = { "hide-b": { onRefresh: (page) => page.widgets.hide("b") } };
    const engine = makeEngine();

    await engine.refresh();

    expect(drawn(engine)).toEqual(["a", "b"]);
  });

  it("re-runs when a Client Script naming it changes on the server", async () => {
    const engine = makeEngine();
    await engine.refresh();
    expect(drawn(engine)).toEqual(["a", "b"]);

    stored.board = { "hide-b": { onRefresh: (page) => page.widgets.hide("b") } };
    invalidateClientScripts(DOCTYPE, "board");

    await vi.waitFor(() => expect(drawn(engine)).toEqual(["a"]));
  });

  it("stops re-running once the reader leaves", async () => {
    const engine = makeEngine();
    await engine.refresh();
    engine.leave();

    stored.board = { "hide-b": { onRefresh: (page) => page.widgets.hide("b") } };
    invalidateClientScripts(DOCTYPE, "board");
    await nextTick();

    expect(call).toHaveBeenCalledTimes(1);
  });

  it("must name itself, so another app's same-named page cannot lend it scripts", () => {
    expect(() => makeEngine("acme", "")).toThrow(/must name itself with pageName/);
  });
});
