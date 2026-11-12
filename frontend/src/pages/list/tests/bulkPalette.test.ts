// The bulk actions as the palette sees them: real dispatcher, real bar layout, a stub List page.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, nextTick, ref, type App } from "vue";
import { acts, type ActEntry } from "@/acts/dispatcher";
import type { ListMeta } from "@/list/defaults";
import { useBulkScope } from "@/list/useBulkScope";
import { createListPageLists } from "@/listPage/createListPage";
import { useBulkBar } from "../useBulkBar";

let mounted: { app: App; release: () => void } | null = null;
afterEach(() => {
  mounted?.release();
  mounted?.app.unmount();
  mounted = null;
});

interface BarOptions {
  rights?: boolean;
  script?: boolean;
  selected?: string[];
  cap?: number;
  locked?: boolean;
  total?: number;
  approx?: boolean;
  meta?: ListMeta | null;
}

async function bar({
  rights = true,
  script = true,
  selected = ["A", "B", "C"],
  cap = 500,
  locked = false,
  total = selected.length,
  approx = false,
  meta = null,
}: BarOptions = {}) {
  // `script: false` leaves the list with Delete only.
  const lists = createListPageLists();
  const selection = ref(selected);
  // A stable array: a rows function that derives a new one each call loops the scope's watcher.
  const loaded = selected.map((name) => ({ name }));
  const askDelete = vi.fn();
  const seen = vi.fn();
  let release = () => {};
  let result!: ReturnType<typeof useBulkBar>;
  const host = {
    lists,
    acts: (supply: () => ActEntry[]) => {
      release = acts.register({
        surfaces: { list: supply },
        context: () => ({}),
        passes: () => rights,
        settled: () => undefined,
        hold: async (work) => work(),
        failed: () => {},
      });
      return {
        context: () => ({}),
        drawn: (name: string) => acts.find(`list.${name}`),
        perform: (act: { name: string }, value?: unknown) =>
          void acts.perform(act.name, value),
      };
    },
  };
  const app = createApp(
    defineComponent({
      setup() {
        result = useBulkBar({
          host: host as never,
          doctype: "ToDo",
          meta: ref(meta),
          askEdit: vi.fn(),
          askExport: vi.fn(),
          copy: vi.fn(),
          selection,
          scope: useBulkScope({
            selection,
            rows: () => loaded as never,
            filters: () => ({}),
            rowsQuery: () => null,
            hasNextPage: () => total > loaded.length,
            totalCount: () => total,
            totalApprox: () => approx,
            exact: () => true,
          }),
          rows: ref([]),
          rowActions: ref([]),
          reload: () => {},
          askDelete,
          cursor: ref(null),
          table: () => null,
        });
        return () => null;
      },
    }),
  );
  app
    .provide("boot", { bulk_actions: !locked, bulk_operation_limit: cap, session: { user: { name: "jane@example.com" } } })
    .mount(document.createElement("div"));
  mounted = { app, release: () => release() };
  if (script)
    lists.bulkActions.add({
      name: "restore",
      label: "Restore",
      run: (_page, names) => seen(names),
    });
  await result.load();
  return { result, selection, askDelete, seen, lists, scope: result.scope };
}

const paletteLabels = () =>
  acts
    .available()
    .filter((act) => act.palette !== false && act.name.startsWith("list."))
    .map((act) => act.label);

describe("the bulk actions in the palette", () => {
  it("offers each bulk action with the selection's scope, and none without a selection", async () => {
    const { selection } = await bar();
    await nextTick();
    expect(paletteLabels()).toEqual(
      expect.arrayContaining(["Restore 3 selected", "Delete 3 selected"]),
    );

    selection.value = [];
    await nextTick();
    expect(paletteLabels().filter((label) => /selected/.test(label!))).toEqual(
      [],
    );
  });

  it("keeps the bar's own labels unscoped", async () => {
    const { result } = await bar();
    await nextTick();
    const labels = result.layout.value.menu.flatMap((group) =>
      group.options.map((option) => option.label),
    );
    expect(labels).toEqual([
      "Restore",
      "Clear assignment",
      "Apply assignment rule",
      "Remove tags",
      "Share",
      "Print",
      "Copy to Clipboard",
      "Export",
      "Delete",
    ]);
  });

  it("runs a script's action from the palette on the selection", async () => {
    const { seen, selection } = await bar();
    await acts.perform("list.restore");
    expect(seen).toHaveBeenCalledWith(["A", "B", "C"]);
    await acts.perform("list.restore", "an option the palette picked");
    expect(seen).toHaveBeenLastCalledWith(["A", "B", "C"]);
    selection.value = ["Z"];
    expect(seen.mock.calls[0][0]).toEqual(["A", "B", "C"]);
  });

  it("offers a script's item without a label, a palette flag or an argument as the bar does", async () => {
    const { lists } = await bar();
    lists.bulkActions.add({ name: "nameless", run: () => {} });
    lists.bulkActions.add({
      name: "quiet",
      label: "Quiet",
      palette: false,
      run: () => {},
    });
    lists.bulkActions.add({
      name: "pick",
      label: "Pick",
      argument: { label: "Which", options: () => [] },
      run: () => {},
    });
    await nextTick();
    expect(paletteLabels()).not.toContain("Quiet 3 selected");
    expect(
      paletteLabels().filter((label) => /^nameless/.test(label ?? "")),
    ).toEqual([]);
    expect(acts.find("list.pick")?.argument).toBeUndefined();
    expect(paletteLabels()).toContain("Pick 3 selected");
  });

  // Print, Copy and Export are uncapped, so they stay offered past the cap.
  const overCap = () =>
    paletteLabels().filter(
      (label) => /selected/.test(label!) && !/^(Print|Copy|Export)/.test(label!),
    );

  it("flips with the selection: at the cap offered, past it left out", async () => {
    const { selection } = await bar({ cap: 3 });
    await nextTick();
    expect(paletteLabels()).toContain("Delete 3 selected");
    selection.value = ["A", "B", "C", "D"];
    await nextTick();
    expect(overCap()).toEqual([]);
  });

  it("runs Delete from the palette", async () => {
    const { askDelete } = await bar();
    await acts.perform("list.delete");
    expect(askDelete).toHaveBeenCalledOnce();
  });

  it("keeps Delete's right: a person without it gets no Delete", async () => {
    await bar({ rights: false });
    await nextTick();
    expect(paletteLabels()).not.toContain("Delete 3 selected");
    expect(paletteLabels()).toContain("Restore 3 selected");
  });

  it("leaves out every action over the cap, and all of them when the switch is off", async () => {
    await bar({ cap: 2 });
    await nextTick();
    expect(overCap()).toEqual([]);
    mounted!.release();
    mounted!.app.unmount();

    await bar({ locked: true });
    await nextTick();
    expect(paletteLabels().filter((label) => /selected/.test(label!))).toEqual(
      [],
    );
  });

  it("shows Open Bulk Actions only while the More menu has something in it", async () => {
    await bar();
    await nextTick();
    expect(acts.find("list.open_bulk_menu")).toBeDefined();
    mounted!.release();
    mounted!.app.unmount();

    const { result } = await bar({ rights: false, script: false });
    await nextTick();
    // Copy to Clipboard needs no right, so a person with none still has a menu.
    expect(result.layout.value.menu.flatMap((group) => group.options.map((option) => option.label))).toEqual([
      "Copy to Clipboard",
    ]);
    expect(acts.find("list.open_bulk_menu")).toBeDefined();
    expect(acts.find("list.clear_selection")).toBeDefined();
  });

  describe("after Select all", () => {
    const everything = { total: 1240, cap: 5000, selected: ["A", "B", "C"] };

    it("offers Delete for all the matching records and nothing that takes row names", async () => {
      const { scope } = await bar(everything);
      scope.selectAll();
      await nextTick();
      expect(paletteLabels()).toContain("Delete all 1,240 matching");
      expect(paletteLabels().filter((label) => /Restore/.test(label!))).toEqual([]);
      expect(paletteLabels().filter((label) => /selected/.test(label!))).toEqual([]);
    });

    it("writes a floor total with a plus", async () => {
      const { scope } = await bar({ selected: ["A", "B"], total: 10000, approx: true, cap: 20000 });
      scope.selectAll();
      await nextTick();
      expect(paletteLabels()).toContain("Delete all 10,000+ matching");
    });

    it("offers Submit, Cancel and the workflow actions on the whole scope", async () => {
      const { scope, result } = await bar({ ...everything, meta: { is_submittable: 1 } });
      scope.selectAll();
      await nextTick();
      expect(paletteLabels()).toEqual(
        expect.arrayContaining(["Submit all 1,240 matching", "Cancel all 1,240 matching"]),
      );
      const bar_ = result.layout.value.menu.flatMap((group) => group.options);
      expect(bar_.filter((option) => !option.disabled).map((option) => option.label)).toEqual([
        "Clear assignment",
        "Apply assignment rule",
        "Remove tags",
        "Share",
        "Print",
        "Export",
        "Submit",
        "Cancel",
        "Delete",
      ]);
    });

    it("follows the bar's cap rule: at the cap offered, over it every entry is left out", async () => {
      const { scope } = await bar({ ...everything, total: 1240, cap: 1240, meta: { is_submittable: 1 } });
      scope.selectAll();
      await nextTick();
      expect(paletteLabels()).toEqual(
        expect.arrayContaining(["Delete all 1,240 matching", "Submit all 1,240 matching"]),
      );
      mounted!.release();
      mounted!.app.unmount();

      const over = await bar({ ...everything, total: 1241, cap: 1240, meta: { is_submittable: 1 } });
      over.scope.selectAll();
      await nextTick();
      expect(paletteLabels().filter((label) => /matching/.test(label!))).toEqual([]);
    });

    it("returns to the selection's wording when the scope clears", async () => {
      const { scope } = await bar(everything);
      scope.selectAll();
      await nextTick();
      scope.clear();
      await nextTick();
      expect(paletteLabels().filter((label) => /matching/.test(label!))).toEqual([]);
    });
  });
});
