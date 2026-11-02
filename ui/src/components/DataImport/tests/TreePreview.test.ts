import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, ref } from "vue";
import type { App } from "vue";
import type { DataImportDoc, DataImportPreview } from "../types";
import type { UseDataImport } from "../useDataImport";

// Menus don't open in happy-dom, so each Actions menu renders its items (and submenus) inline.
vi.mock("frappe-ui", async (importOriginal) => {
  const actual = await importOriginal<typeof import("frappe-ui")>();
  type Item = {
    label: string;
    onClick?: () => void;
    submenu?: Item[];
    disabled?: boolean;
  };
  const renderItems = (items: Item[], path: string): any[] =>
    items.flatMap((item) => [
      h(
        "button",
        {
          "data-menu-item": path + item.label,
          disabled: item.disabled,
          onClick: item.onClick,
        },
        item.label
      ),
      ...(item.submenu ? renderItems(item.submenu, `${item.label} > `) : []),
    ]);
  const Dropdown = defineComponent({
    props: ["options"],
    emits: ["update:open"],
    setup(props, { slots, emit }) {
      return () =>
        h("div", { "data-dropdown": "" }, [
          h(
            "span",
            { "data-open-menu": "", onClick: () => emit("update:open", true) },
            slots.default?.()
          ),
          ...renderItems(props.options, ""),
        ]);
    },
  });
  return { ...actual, Dropdown };
});

import PreviewStep from "../steps/PreviewStep.vue";
import TreePreview from "../steps/TreePreview.vue";

let app: App | undefined;
let host: HTMLElement | undefined;

afterEach(() => {
  app?.unmount();
  host?.remove();
  document.body.innerHTML = "";
  app = undefined;
  host = undefined;
});

type Node = {
  id: string;
  label: string;
  parent: string | null;
  row_number: number;
  is_group: number;
  orig_parent?: string | null;
  orig_is_group?: number;
  orphan?: boolean;
  warnings?: string[];
};

function node(n: Node) {
  return {
    orig_parent: n.parent,
    orig_is_group: n.is_group,
    warnings: [],
    ...n,
  };
}

// All -> Asia -> India, All -> Europe; Lone is a leaf at the top; Loop is in a parent cycle.
function makeNodes() {
  return [
    node({ id: "All", label: "All", parent: null, row_number: 2, is_group: 1 }),
    node({
      id: "Asia",
      label: "Asia",
      parent: "All",
      row_number: 3,
      is_group: 1,
    }),
    node({
      id: "India",
      label: "India",
      parent: "Asia",
      row_number: 4,
      is_group: 0,
      warnings: ["Parent <strong>X</strong> not found in file"],
    }),
    node({
      id: "Europe",
      label: "Europe",
      parent: "All",
      row_number: 5,
      is_group: 1,
    }),
    node({
      id: "Lone",
      label: "Lone",
      parent: null,
      row_number: 6,
      is_group: 0,
    }),
    node({
      id: "Loop",
      label: "Loop",
      parent: "Loop",
      row_number: 7,
      is_group: 1,
    }),
  ];
}

function makeDoc(overrides: Partial<DataImportDoc> = {}): DataImportDoc {
  return {
    doctype: "Data Import",
    name: "DI-1",
    reference_doctype: "CRM Territory",
    import_type: "Insert New Records",
    status: "Pending",
    import_file: "/private/files/territory.csv",
    google_sheets_url: null,
    mute_emails: 1,
    submit_after_import: 0,
    use_csv_sniffer: 0,
    custom_delimiters: 0,
    template_options: null,
    value_mappings: [],
    skipped_rows: [],
    ...overrides,
  };
}

function makePreview(
  treePreview?: Record<string, any> | null
): DataImportPreview {
  return {
    columns: [{ header_title: "Sr. No", skip_import: true }],
    data: [[2], [3]],
    warnings: [],
    import_log: [],
    total_number_of_rows: 6,
    ...(treePreview === null
      ? {}
      : {
          tree_preview: {
            nodes: makeNodes(),
            tree_warnings: [{ row: 4, message: "Parent X not found in file" }],
            total_nodes: 6,
            editable: true,
            is_group_editable: true,
            parent_field: "parent_crm_territory",
            ...treePreview,
          },
        }),
  };
}

function fakeDataImport({
  doc = makeDoc(),
  preview = makePreview() as DataImportPreview | null,
} = {}) {
  const fake = {
    doc: ref(doc),
    saving: ref(false),
    preview: ref(preview),
    previewLoading: ref(false),
    previewError: ref(null),
    providerSchema: ref(null),
    doctypeMeta: ref([]),
    save: vi.fn(async () => fake.doc.value),
  };
  return fake;
}

async function mount(
  fake: ReturnType<typeof fakeDataImport>,
  component: any = TreePreview
) {
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({
    render: () =>
      h(component, { dataImport: fake as unknown as UseDataImport }),
  });
  app.mount(host);
  await nextTick();
  await nextTick();
  return host;
}

const labels = (el: HTMLElement) =>
  [...el.querySelectorAll<HTMLElement>("[data-tree-row]")].map(
    (row) => row.querySelector(".truncate")!.textContent
  );
const row = (el: HTMLElement, label: string) =>
  [...el.querySelectorAll<HTMLElement>("[data-tree-row]")].find(
    (r) => r.querySelector(".truncate")!.textContent === label
  )!;
const button = (el: HTMLElement, label: string) =>
  [...el.querySelectorAll<HTMLButtonElement>("button")].find(
    (b) => b.textContent?.trim() === label
  )!;

async function openMenu(el: HTMLElement, label: string) {
  row(el, label).querySelector<HTMLElement>("[data-open-menu]")!.click();
  await nextTick();
}
async function pick(el: HTMLElement, label: string, item: string) {
  await openMenu(el, label);
  row(el, label)
    .querySelector<HTMLButtonElement>(`[data-menu-item="${item}"]`)!
    .click();
  await nextTick();
}

describe("TreePreview", () => {
  it("shows the Tree / Table switch only when the preview has a tree", async () => {
    const tree = await mount(fakeDataImport(), PreviewStep);
    expect(button(tree, "Tree")).toBeTruthy();
    expect(button(tree, "Table")).toBeTruthy();
    expect(labels(tree)).toContain("All");
    app!.unmount();

    const flat = await mount(
      fakeDataImport({ preview: makePreview(null) }),
      PreviewStep
    );
    expect(button(flat, "Tree")).toBeUndefined();
    expect(flat.querySelector("table")).toBeTruthy();
  });

  it("starts fully expanded, with warnings, orphans and the node count", async () => {
    const el = await mount(fakeDataImport());
    expect(labels(el)).toEqual([
      "All",
      "Asia",
      "India",
      "Europe",
      "Lone",
      "Loop",
    ]);
    expect(el.textContent).toContain("1 warning found.");
    expect(row(el, "India").querySelector("[data-tree-warning]")).toBeTruthy();
    expect(row(el, "Loop").textContent).toContain("(unlinked)");
    expect(row(el, "Lone").textContent).not.toContain("(unlinked)");
    expect(el.textContent).toContain("Tree preview of 6 nodes");
  });

  it("filters by label or #row and keeps the ancestors of matches", async () => {
    const el = await mount(fakeDataImport());
    const input = el.querySelector<HTMLInputElement>('input[type="search"]')!;
    input.value = "ind";
    input.dispatchEvent(new Event("input"));
    await nextTick();
    expect(labels(el)).toEqual(["All", "Asia", "India"]);

    input.value = "#5";
    input.dispatchEvent(new Event("input"));
    await nextTick();
    expect(labels(el)).toEqual(["All", "Europe"]);
  });

  it("collapses and expands all, disabling the button that has nothing to do", async () => {
    const el = await mount(fakeDataImport());
    expect(button(el, "Expand all").disabled).toBe(true);
    button(el, "Collapse all").click();
    await nextTick();
    expect(labels(el)).toEqual(["All", "Lone", "Loop"]);
    expect(button(el, "Collapse all").disabled).toBe(true);
    button(el, "Expand all").click();
    await nextTick();
    expect(labels(el)).toEqual([
      "All",
      "Asia",
      "India",
      "Europe",
      "Lone",
      "Loop",
    ]);
  });

  it("moves a node under a valid group and saves the override", async () => {
    const fake = fakeDataImport();
    const el = await mount(fake);
    await openMenu(el, "Asia");
    const targets = [
      ...row(el, "Asia").querySelectorAll<HTMLElement>(
        '[data-menu-item^="Move to… > "]'
      ),
    ].map((b) => b.textContent);
    // not itself, its current parent or a descendant, and only groups
    expect(targets).toEqual(["Top level", "Europe", "Loop"]);

    await pick(el, "Asia", "Move to… > Europe");
    expect(JSON.parse(fake.doc.value.tree_parent_overrides!)).toEqual({
      3: { parent: "Europe" },
    });
    expect(fake.save).toHaveBeenCalledTimes(1);
    expect(labels(el)).toEqual([
      "All",
      "Europe",
      "Asia",
      "India",
      "Lone",
      "Loop",
    ]);
    expect(row(el, "Asia").textContent).toContain("Edited");
  });

  it("moves a node to the top level, and only offers Top level to nodes with a parent", async () => {
    const fake = fakeDataImport();
    const el = await mount(fake);
    await openMenu(el, "Lone");
    expect(
      row(el, "Lone").querySelector('[data-menu-item="Move to… > Top level"]')
    ).toBeNull();

    await pick(el, "India", "Move to… > Top level");
    expect(JSON.parse(fake.doc.value.tree_parent_overrides!)).toEqual({
      4: { parent: "" },
    });
    expect(fake.save).toHaveBeenCalledTimes(1);
  });

  it("an orphan moved into the tree is no longer unlinked", async () => {
    const el = await mount(fakeDataImport());
    await pick(el, "Loop", "Move to… > Europe");
    expect(row(el, "Loop").textContent).not.toContain("(unlinked)");
  });

  it("marks a node as group or leaf; a group with children can't become a leaf", async () => {
    const fake = fakeDataImport();
    const el = await mount(fake);
    await openMenu(el, "Asia");
    expect(
      row(el, "Asia").querySelector('[data-menu-item="Mark as leaf"]')
    ).toBeNull();

    await pick(el, "Lone", "Mark as group");
    expect(JSON.parse(fake.doc.value.tree_parent_overrides!)).toEqual({
      6: { is_group: 1 },
    });
    await pick(el, "Europe", "Mark as leaf");
    expect(JSON.parse(fake.doc.value.tree_parent_overrides!)).toEqual({
      5: { is_group: 0 },
      6: { is_group: 1 },
    });
    expect(fake.save).toHaveBeenCalledTimes(2);
  });

  it("Reset node removes that node's override, Reset all clears them", async () => {
    const nodes = makeNodes();
    nodes[1].parent = "Europe"; // Asia moved, as the server sends it back
    nodes[4].is_group = 1; // Lone marked as group
    const fake = fakeDataImport({
      doc: makeDoc({
        tree_parent_overrides: JSON.stringify({
          3: { parent: "Europe" },
          6: { is_group: 1 },
        }),
      }),
      preview: makePreview({ nodes }),
    });
    const el = await mount(fake);
    expect(row(el, "Asia").textContent).toContain("Edited");

    await pick(el, "Asia", "Reset node");
    expect(JSON.parse(fake.doc.value.tree_parent_overrides!)).toEqual({
      6: { is_group: 1 },
    });
    expect(row(el, "Asia").textContent).not.toContain("Edited");

    button(el, "Reset all").click();
    await nextTick();
    expect(fake.doc.value.tree_parent_overrides).toBe("");
    expect(fake.save).toHaveBeenCalledTimes(2);
    expect(button(el, "Reset all")).toBeUndefined();
  });

  it("is read-only once the import is complete, keeping Edited but dropping warnings", async () => {
    const nodes = makeNodes();
    nodes[1].parent = "Europe";
    const el = await mount(
      fakeDataImport({
        doc: makeDoc({ status: "Partial Success" }),
        preview: makePreview({ nodes }),
      })
    );
    expect(el.querySelector("[data-dropdown]")).toBeNull();
    expect(button(el, "Reset all")).toBeUndefined();
    expect(row(el, "Asia").textContent).toContain("Edited");
    expect(el.textContent).not.toContain("warning found");
    expect(el.querySelector("[data-tree-warning]")).toBeNull();
  });

  it("clicking a node highlights its row in the table", async () => {
    const el = await mount(fakeDataImport(), PreviewStep);
    row(el, "Asia").click();
    await nextTick();
    const tableTab = button(el, "Table");
    tableTab.dispatchEvent(
      new MouseEvent("mousedown", { bubbles: true, button: 0 })
    );
    await new Promise((resolve) => setTimeout(resolve));
    expect(el.querySelector("tr[data-highlighted]")?.textContent).toContain(
      "3"
    );
  });

  it("says when the file has no tree nodes", async () => {
    const el = await mount(
      fakeDataImport({ preview: makePreview({ nodes: [], total_nodes: 0 }) })
    );
    expect(el.textContent).toContain(
      "No valid tree nodes found in the import file."
    );
    expect(el.querySelector("[data-tree-row]")).toBeNull();
  });
});
