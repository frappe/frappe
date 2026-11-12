// A field change re-runs `onRefresh` once, inside the hold that runs the field's handler.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ref, watchEffect } from "vue";

vi.mock("frappe-ui", () => ({
  call: vi.fn(),
  toast: { success: vi.fn(), error: vi.fn() },
  createResource: () => ({
    data: null,
    loading: false,
    fetch() {},
    reload() {},
  }),
  frappeRequest: vi.fn(),
}));
vi.mock("@framework/ui/api", () => ({
  runMethod: vi.fn(async () => ({ data: null })),
  getMeta: vi.fn(async () => ({ data: null })),
}));

import { createRecordPage, SAVE_VETO, type RecordPageHost } from "../createRecordPage";
import { HOST_SOURCE, runningSource, withRegisteringSource } from "@/pageEngine/context";
import { registerRecordPage, resetRegistry } from "../registry";
import type { AuthoredHandlers, RecordPageApi } from "../types";

const RECORD_TABS = [
  { name: "details", label: "Details" },
  { name: "activity", label: "Activity" },
];

function makePage(overrides: Partial<RecordPageHost> = {}) {
  const moved: { tab: string; drawn: string[] }[] = [];
  const host: RecordPageHost = {
    app: "frappe",
    doctype: "CRM Deal",
    docname: "CRM-DEAL-1",
    doc: ref({}),
    saved: ref({}),
    meta: ref(null),
    perms: () => ({}),
    isDirty: () => true,
    activeTab: () => "details",
    activateTab: (tab) =>
      void moved.push({ tab, drawn: controller.tabs.visible().map((one) => one.name) }),
    save: async () => {},
    reload: async () => {},
    router: {} as any,
    activityRows: () => [],
    scrollToActivity: async () => true,
    reloadActivity: async () => {},
    fileRows: () => [],
    reloadFiles: async () => {},
    ...overrides,
  };
  const controller = createRecordPage(host);
  controller.tabs.provideBuiltins(() => RECORD_TABS as any[]);
  return { controller, page: controller.page, moved };
}

/** How many times each drawn overlay changed, counted by a sync effect over its `resolve()`. */
function countPaints(controller: ReturnType<typeof makePage>["controller"]) {
  const paints = { count: -1, fields: -1, formTabs: -1 };
  const count = (key: keyof typeof paints, read: () => unknown) =>
    watchEffect(
      () => {
        read();
        paints[key] += 1;
      },
      { flush: "sync" },
    );
  count("count", () => controller.quickActions.resolve());
  count("fields", () => controller.fields.resolve());
  count("formTabs", () => controller.form.tabs.resolve());
  return paints;
}

function register(source: string, handlers: AuthoredHandlers) {
  return withRegisteringSource(source, async () => registerRecordPage("CRM Deal", handlers));
}

const row = { parentfield: "items", key: "row-1" };

const drawn = (controller: ReturnType<typeof makePage>["controller"]) =>
  controller.quickActions.visible().map((one) => one.name);

/** Opens a page whose `onRefresh` and `qty` handler append to `log`, so a test reads their order. */
async function openLogged(extra: AuthoredHandlers = {}, host: Partial<RecordPageHost> = {}) {
  const log: string[] = [];
  await register("deal", {
    onRefresh: (page: RecordPageApi) => {
      log.push(`refresh:${page.doc.qty}`);
      page.fields.hide("rate");
    },
    qty: () => void log.push("qty"),
    beforeSave: () => void log.push("beforeSave"),
    ...extra,
  });
  const made = makePage(host);
  await made.controller.refresh();
  log.length = 0;
  return { ...made, log };
}

beforeEach(() => {
  resetRegistry();
  vi.spyOn(console, "warn").mockImplementation(() => {});
  vi.spyOn(console, "error").mockImplementation(() => {});
});

describe("a field change re-runs onRefresh", () => {
  it("runs the field's handler, then `onRefresh` once, which reads the new value", async () => {
    const { controller, page, log } = await openLogged();

    page.doc.qty = 3;
    await controller.commits.commit("qty", 3);

    expect(log).toEqual(["qty", "refresh:3"]);
  });

  it("re-runs it for a field with no handler", async () => {
    const { controller, log } = await openLogged();

    await controller.commits.commit("rate", 5);

    expect(log).toEqual(["refresh:undefined"]);
  });

  it("paints the change and the re-run in one write", async () => {
    const { controller, page } = await openLogged({
      onRefresh: (page: RecordPageApi) => {
        if (page.doc.qty > 2) page.quickActions.add({ name: "bulk", label: "bulk", run: () => {} });
      },
    });
    const paints = countPaints(controller);

    page.doc.qty = 3;
    await controller.commits.commit("qty", 3);

    expect(drawn(controller)).toEqual(["bulk"]);
    expect(paints.count).toBe(1);
  });

  it("re-runs it for a child row's field and for a row added or removed", async () => {
    const { controller, log } = await openLogged({
      "items.qty": () => void log.push("items.qty"),
    });

    await controller.commits.commit("qty", 2, row);
    controller.commits.rowChanged(row, "add");
    await controller.commits.flush();
    await vi.waitFor(() => expect(log.filter((entry) => entry.startsWith("refresh"))).toHaveLength(2));

    expect(log[0]).toBe("items.qty");
  });

  it("does not re-run it for an echo of the value already committed", async () => {
    const { controller, log } = await openLogged();

    await controller.commits.commit("qty", 3);
    await controller.commits.commit("qty", 3);

    expect(log).toEqual(["qty", "refresh:undefined"]);
  });

  it("does not re-run it for a Button's click, which commits no value", async () => {
    const { controller, log } = await openLogged({ run_it: () => void log.push("run_it") });

    controller.commits.trigger("run_it");
    await controller.commits.flush();

    expect(log).toEqual(["run_it"]);
  });

  it("re-runs it for an edit a save flushes, before `beforeSave`", async () => {
    const { controller, page, log } = await openLogged();

    page.doc.qty = 4;
    controller.commits.pending("qty", 4);
    await page.save();

    expect(log.slice(0, 3)).toEqual(["qty", "refresh:4", "beforeSave"]);
  });

  it("paints a flushed edit's re-run once, as an edit outside a save does", async () => {
    const { controller, page } = await openLogged({
      onRefresh: (page: RecordPageApi) => {
        if (page.doc.qty > 2) page.quickActions.add({ name: "bulk", label: "bulk", run: () => {} });
      },
    });
    const paints = countPaints(controller);

    page.doc.qty = 4;
    controller.commits.pending("qty", 4);
    await page.save();

    expect(drawn(controller)).toEqual(["bulk"]);
    expect(paints.count).toBe(1);
  });
});

const FIELDS = [
  { fieldname: "qty", fieldtype: "Int", label: "Qty" },
  { fieldname: "rate", fieldtype: "Currency", label: "Rate" },
  { fieldname: "discount", fieldtype: "Percent", label: "Discount" },
  { fieldname: "items", fieldtype: "Table", label: "Items", options: "Deal Item" },
];
const withFields = (): Partial<RecordPageHost> => ({
  meta: ref({ fields: FIELDS }) as any,
  doc: ref({ items: [{ name: "r1", item: "Bolt" }] }) as any,
});
/** A promise a test settles by hand, to hold a handler open. */
function gate() {
  let open = () => {};
  const promise = new Promise<void>((resolve) => (open = resolve));
  return { promise, open };
}
const action = (name: string) => ({ name, label: name, run: () => {} });

describe("what a field handler draws outlasts that edit's re-run", () => {
  it("keeps the handler's quick action, next to what `onRefresh` draws", async () => {
    const { controller } = await openLogged(
      {
        onRefresh: (page: RecordPageApi) => page.quickActions.add(action("built")),
        qty: (page: RecordPageApi) => page.quickActions.add(action("handler")),
      },
      withFields(),
    );
    const paints = countPaints(controller);

    await controller.commits.commit("qty", 3);

    expect(drawn(controller)).toEqual(["built", "handler"]);
    expect(paints.count).toBe(1);
  });

  it("keeps the handler's `setError`", async () => {
    const { controller } = await openLogged(
      { qty: (page: RecordPageApi) => page.fields.setError("qty", "Too big") },
      withFields(),
    );

    await controller.commits.commit("qty", 3);

    expect(controller.fieldErrors.drawn.value).toEqual({ qty: "Too big" });
  });

  it("keeps the `setError` a handler puts on a child row's cell", async () => {
    const { controller } = await openLogged(
      { "items.qty": (page: RecordPageApi) => page.rows("items")[0].setError("item", "Not stocked") },
      withFields(),
    );

    await controller.commits.commit("qty", 3, { parentfield: "items", key: "name:r1" });

    expect(Object.values(controller.fieldErrors.drawn.value)).toEqual(["Not stocked"]);
  });

  it("keeps a handler's `clearError`, so a mark `onRefresh` sets is gone", async () => {
    const { controller } = await openLogged(
      {
        onRefresh: (page: RecordPageApi) => page.fields.setError("rate", "Set by onRefresh"),
        qty: (page: RecordPageApi) => page.fields.clearError("rate"),
      },
      withFields(),
    );
    await controller.refresh();
    expect(controller.fieldErrors.drawn.value).toEqual({ rate: "Set by onRefresh" });

    await controller.commits.commit("qty", 3);

    expect(controller.fieldErrors.drawn.value).toEqual({});
  });

  it("keeps the handler's hidden field, next to the one `onRefresh` hides", async () => {
    const { controller } = await openLogged(
      { qty: (page: RecordPageApi) => page.fields.hide("discount") },
      withFields(),
    );

    await controller.commits.commit("qty", 3);

    expect(controller.fields.isDrawn("discount")).toBe(false);
    expect(controller.fields.isDrawn("rate")).toBe(false);
  });

  it("keeps the types the handler gave the Activity tab", async () => {
    const { controller } = await openLogged({
      qty: (page: RecordPageApi) => page.activity.types(["comment"]),
    });

    await controller.commits.commit("qty", 3);

    expect(controller.activity.shownTypes()).toEqual(["comment"]);
  });

  it("drops them at the next edit's re-run, as `page.refresh()` does", async () => {
    const { controller } = await openLogged(
      {
        qty: (page: RecordPageApi) => {
          page.fields.setError("qty", "Too big");
          page.quickActions.add(action("handler"));
          page.activity.types(["comment"]);
        },
      },
      withFields(),
    );

    await controller.commits.commit("qty", 3);
    await controller.commits.commit("rate", 5);

    expect(controller.fieldErrors.drawn.value).toEqual({});
    expect(drawn(controller)).toEqual([]);
    expect(controller.activity.shownTypes()).toBeNull();
  });

  it("does not keep a mark the reader's next edit of that field cleared", async () => {
    const { controller } = await openLogged(
      { qty: (page: RecordPageApi) => page.fields.setError("qty", "Too big") },
      withFields(),
    );
    await controller.commits.commit("qty", 3);

    controller.commits.pending("qty", 4);

    expect(controller.fieldErrors.drawn.value).toEqual({});
  });

  it("does not keep what `beforeSave` drew, which the refresh after the write replaces", async () => {
    let refresh = async () => {};
    const { controller, page } = await openLogged(
      { beforeSave: (page: RecordPageApi) => page.quickActions.add(action("before")) },
      { save: () => refresh() },
    );
    refresh = () => controller.refresh();

    await page.save();

    expect(drawn(controller)).toEqual([]);
  });

  it("closes overlapping holds apart: a slow handler's close does not turn the save's draws into kept ones", async () => {
    const edit = gate();
    const before = gate();
    let refresh = async () => {};
    const { controller, page } = await openLogged(
      {
        qty: async () => void (await edit.promise),
        beforeSave: async (page: RecordPageApi) => {
          await before.promise;
          page.quickActions.add(action("before"));
        },
      },
      { save: () => refresh() },
    );
    refresh = () => controller.refresh();

    const editing = controller.commits.commit("qty", 3);
    const saving = page.save();
    edit.open();
    await editing;
    before.open();
    await saving;

    expect(drawn(controller)).toEqual([]);
  });

  it("keeps only the last edit's own draws when two slow edits overlap", async () => {
    const early = gate();
    const late = gate();
    const { controller } = await openLogged(
      {
        qty: async (page: RecordPageApi) => {
          page.quickActions.add(action("a"));
          await early.promise;
        },
        rate: async (page: RecordPageApi) => {
          await late.promise;
          page.quickActions.add(action("b"));
        },
      },
      withFields(),
    );

    const first = controller.commits.commit("qty", 3);
    const second = controller.commits.commit("rate", 5);
    early.open();
    await first;
    late.open();
    await second;

    expect(drawn(controller)).toEqual(["b"]);
  });
});
