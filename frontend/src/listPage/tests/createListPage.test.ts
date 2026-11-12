// The list page on the page engine: it paints once its list.js files are in, runs their `onRefresh`
// on its four lists, and reads its rows and selection from the renderer.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";

vi.mock("frappe-ui", () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
  dialog: vi.fn(),
}));
vi.mock("@framework/ui/api", () => ({ runMethod: vi.fn() }));

import type { View } from "@/list/view";
import { createListPage, type ListPageController } from "../createListPage";
import type { ListPermissions } from "../listPermissions";
import { addListScript } from "@/contributions/registry";
import type { ListPageApi } from "../types";

let doctype = "";
let count = 0;
const pages: ListPageController[] = [];

beforeEach(() => {
  // The loader keeps its scripts for the session; each test takes a doctype of its own.
  doctype = `List Page Doctype ${++count}`;
  vi.spyOn(console, "warn").mockImplementation(() => {});
});

afterEach(() => {
  pages.splice(0).forEach((one) => one.leave());
  vi.restoreAllMocks();
});

const permissions: ListPermissions = {
  perms: () => ({ read: 1 }),
  roles: () => ["System Manager"],
  passes: () => true,
  loading: () => false,
  ready: () => Promise.resolve(),
};

function makeView(): View {
  return {
    doctype,
    key: "list",
    type: "List",
    filters: ref([]),
    sort: ref([]),
  } as unknown as View;
}

function makePage(view = makeView()) {
  const list = createListPage({ view, router: {} as never, meta: () => null, permissions });
  list.lists.columns.provideBuiltins(() => [{ name: "status" }, { name: "enabled", label: "Enabled" }]);
  pages.push(list);
  return list;
}

function addScript(onRefresh: (page: ListPageApi) => void) {
  let land!: () => void;
  const landed = new Promise<void>((resolve) => (land = resolve));
  addListScript(doctype, { app: "crm", load: () => landed.then(() => ({ default: { onRefresh } })) });
  return land;
}

const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

describe("the list page", () => {
  it("waits for its list.js before it paints, then draws what onRefresh did", async () => {
    const land = addScript((page) => {
      page.columns.update("enabled", { switch: true });
      page.rowActions.add({ name: "duplicate", label: "Duplicate", run: () => {} });
    });
    const list = makePage();

    list.paint();
    await settle();
    expect(list.engine.ready.value).toBe(false);

    land();
    await settle();
    expect(list.engine.ready.value).toBe(true);
    expect(list.lists.columns.visible().find((one) => one.name === "enabled")).toMatchObject({ switch: true });
    expect(list.lists.rowActions.visible().map((one) => one.name)).toEqual(["duplicate"]);
  });

  it("keeps a column's badge function and the fields it reads", async () => {
    const badge = () => ({ theme: "red" as const });
    const land = addScript((page) => page.columns.update("status", { badge, fields: ["due"], unknown: 1 } as never));
    const list = makePage();

    list.paint();
    land();
    await settle();
    const column = list.lists.columns.visible().find((one) => one.name === "status");
    expect(column).toMatchObject({ badge, fields: ["due"] });
    expect(column).not.toHaveProperty("unknown");
  });

  it("paints at once for a doctype with no list.js", async () => {
    const list = makePage();
    list.paint();
    await settle();
    expect(list.engine.ready.value).toBe(true);
  });

  it("reads rows and selection from the renderer, frozen, and none before it attaches", () => {
    const list = makePage();
    expect(list.page.rows).toEqual([]);

    const rows = [{ name: "R-1" }, { name: "R-2" }];
    list.attach({ rows: () => rows, selection: () => ["R-2"], reload: () => {} });
    expect(list.page.rows).toEqual(rows);
    expect(list.page.selection).toEqual(["R-2"]);
    expect(Object.isFrozen(list.page.rows)).toBe(true);
    expect(Object.isFrozen(list.page.selection)).toBe(true);
  });

  it("reloads through the renderer, and not once the reader has left", () => {
    const reload = vi.fn();
    const list = makePage();
    list.attach({ rows: () => [], selection: () => [], reload });

    list.page.reload();
    expect(reload).toHaveBeenCalledTimes(1);
    list.leave();
    list.page.reload();
    expect(reload).toHaveBeenCalledTimes(1);
  });

  it("writes filters and sort to the view, and names the view", () => {
    const view = makeView();
    const list = makePage(view);
    const status = [["status", "=", "Open"]] as unknown as ListPageApi["filters"];

    list.page.filters = status;
    list.page.sort = [["modified", "desc"]] as unknown as ListPageApi["sort"];
    expect(view.filters.value).toEqual(status);
    expect(view.sort.value).toEqual([["modified", "desc"]]);
    expect(list.page.filters).toEqual(status);
    expect(list.page.view).toEqual({ key: "list", type: "List" });
    expect(list.page.doctype).toBe(doctype);
  });

  it("replays when the renderer attaches, so onRefresh sees the built-ins it gives", async () => {
    const seen: boolean[] = [];
    const land = addScript((page) => void seen.push(page.columns.has("title")));
    const list = createListPage({ view: makeView(), router: {} as never, meta: () => null, permissions });
    pages.push(list);
    list.paint();
    land();
    await settle();
    expect(seen).toEqual([false]);

    list.lists.columns.provideBuiltins(() => [{ name: "title" }]);
    list.attach({ rows: () => [], selection: () => [], reload: () => {} });
    await settle();
    expect(seen).toEqual([false, true]);
  });

  it("lets a script hide a built-in control and add its own", async () => {
    const land = addScript((page) => {
      page.controls.hide("sort");
      page.controls.add({ name: "export", label: "Export", run: () => {} });
    });
    const list = makePage();
    list.lists.controls.provideBuiltins(() => [{ name: "filter" }, { name: "sort" }]);
    list.paint();
    land();
    await settle();
    expect(list.lists.controls.visible().map((one) => one.name)).toEqual(["filter", "export"]);
  });
});
