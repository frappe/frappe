// A script's row limits on a Table field reach the grid the record page draws, at once.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, ref } from "vue";
import type { App } from "vue";

vi.mock("frappe-ui", async (importOriginal) => ({
  ...(await importOriginal<typeof import("frappe-ui")>()),
  call: vi.fn(),
  toast: { success: vi.fn(), error: vi.fn() },
  frappeRequest: vi.fn(),
}));
vi.mock("@framework/ui/api", () => ({
  runMethod: vi.fn(async () => ({ data: null })),
  getMeta: vi.fn(async () => ({ data: null })),
}));

import { getFieldComponent } from "@framework/ui/FormLayout";
import { ResolveFieldKey } from "@framework/ui/FormLayout/types";
import type { FieldNode, RawMetaField } from "@framework/ui/FormLayout/types";
import { createRecordPage, type RecordPageHost } from "../createRecordPage";
import { resetFieldWarnings } from "../fields";
import { joinLayout } from "../formLayoutSource/joinLayout";
import { registerRecordPage, resetRegistry } from "../registry";
import { resetRowWarnings } from "../rows";

const FIELDS: RawMetaField[] = [
  { fieldname: "qty", fieldtype: "Int", label: "Qty" },
  { fieldname: "items", fieldtype: "Table", label: "Items", options: "Deal Item" },
];
const CHILD: RawMetaField[] = [{ fieldname: "item", fieldtype: "Data", label: "Item" }];
const TREE = [{ name: "details", sections: [{ name: "main", columns: [{ fields: ["qty", "items"] }] }] }];

const StubField = defineComponent({ setup: () => () => h("input") });

let app: App | undefined;
let root: HTMLElement | undefined;

beforeEach(() => {
  resetRegistry();
  resetFieldWarnings();
  resetRowWarnings();
});

afterEach(() => {
  app?.unmount();
  root?.remove();
  app = root = undefined;
});

function makeHost(): RecordPageHost {
  const doc = ref<Record<string, any>>({ qty: 1, items: [{ name: "r1", item: "Bolt" }] });
  return {
    app: "frappe",
    doctype: "CRM Deal",
    docname: "CRM-DEAL-1",
    doc,
    saved: ref({}),
    meta: ref({ fields: FIELDS }),
    perms: () => ({}),
    isDirty: () => false,
    activeTab: () => "",
    activateTab: () => {},
    formLayout: () => [],
    focusField: () => {},
    childFields: () => CHILD,
    save: async () => {},
    reload: async () => {},
    router: {} as any,
    activityRows: () => [],
    scrollToActivity: async () => true,
    reloadActivity: async () => {},
    fileRows: () => [],
    reloadFiles: async () => {},
  };
}

/** The Table field as the record page's join builds it from the script's overrides. */
function mountGrid(controller: ReturnType<typeof createRecordPage>, host: RecordPageHost) {
  const tableField = (): FieldNode => {
    const [tab] = joinLayout(TREE, FIELDS, {
      childMetas: { "Deal Item": CHILD },
      overrides: controller.fields.resolve(),
    });
    return tab.sections[0].columns[0].fields[1];
  };
  root = document.createElement("div");
  document.body.appendChild(root);
  app = createApp({
    render: () => h(getFieldComponent("Table"), { field: tableField(), modelValue: host.doc.value.items }),
  });
  app.provide(ResolveFieldKey, () => StubField);
  app.mount(root);
}

/** What a control does: write the draft, then commit, which runs the field's handler. */
async function commitQty(controller: ReturnType<typeof createRecordPage>, host: RecordPageHost, qty: number) {
  host.doc.value.qty = qty;
  await controller.commits.commit("qty", qty);
  await nextTick();
}

function buttons(): string[] {
  return [...root!.querySelectorAll("button")].map((button) => button.textContent?.trim() ?? "");
}

async function selectAll() {
  root!.querySelector<HTMLElement>('[aria-label="Select all"]')!.click();
  await nextTick();
}

describe("a script's row limits on a Table field", () => {
  it("hide Add Row and Delete as soon as a field handler sets them, and bring them back when cleared", async () => {
    registerRecordPage("CRM Deal", {
      qty(page) {
        const locked = page.doc.qty > 5 ? 1 : 0;
        page.fields.update("items", { cannot_add_rows: locked, cannot_delete_rows: locked });
      },
    });
    const host = makeHost();
    const controller = createRecordPage(host);
    mountGrid(controller, host);
    await selectAll();
    expect(buttons()).toContain("Add Row");
    expect(buttons().some((label) => label.startsWith("Delete"))).toBe(true);

    await commitQty(controller, host, 9);
    expect(buttons()).not.toContain("Add Row");
    expect(buttons().some((label) => label.startsWith("Delete"))).toBe(false);

    await commitQty(controller, host, 2);
    expect(buttons()).toContain("Add Row");
    expect(buttons().some((label) => label.startsWith("Delete"))).toBe(true);
  });
});
