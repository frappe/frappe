// What `window.desk.state` reads off a record page: edits, errors and the fields the layout shows.
import { afterEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";

vi.mock("frappe-ui", () => ({ toast: { success: vi.fn(), error: vi.fn() }, frappeRequest: vi.fn() }));
vi.mock("@framework/ui/api", () => ({
  runMethod: vi.fn(async () => ({ data: null })),
  getMeta: vi.fn(async () => ({ data: null, children: [] })),
}));

import { acts } from "@/acts/dispatcher";
import { mapField } from "@framework/ui/FormLayout";
import { createRecordPage, type RecordPageHost } from "../createRecordPage";

const META = {
  name: "CRM Deal",
  fields: [
    { fieldname: "status", fieldtype: "Select", label: "Status", options: "Open\nWon", reqd: 1 as const },
    { fieldname: "approved", fieldtype: "Check", label: "Approved" },
    { fieldname: "products", fieldtype: "Table", options: "Deal Product" },
  ],
};

const controllers: ReturnType<typeof createRecordPage>[] = [];

function makePage(overrides: Partial<RecordPageHost> = {}) {
  const field = (name: string) => mapField(META.fields.find((one) => one.fieldname === name)!, {});
  const layout = () =>
    [
      { name: "main", sections: [{ columns: [{ fields: [field("status"), field("products")] }] }] },
      { name: "more", hidden: true, sections: [{ columns: [{ fields: [field("approved")] }] }] },
    ] as any;
  const host: RecordPageHost = {
    app: "frappe",
    doctype: "CRM Deal",
    docname: "CRM-DEAL-1",
    doc: ref({ status: "Open", approved: 0, docstatus: 1, products: [{}, {}] }),
    saved: ref({}),
    meta: ref(META),
    perms: () => ({ read: 1, write: 1 }),
    isDirty: () => true,
    activeTab: () => "details",
    activateTab: () => {},
    save: vi.fn(async () => {}),
    reload: async () => {},
    router: {} as any,
    activityRows: () => [],
    scrollToActivity: async () => true,
    reloadActivity: async () => {},
    fileRows: () => [],
    reloadFiles: async () => {},
    childFields: () => [],
    formLayout: layout,
    ...overrides,
  };
  const controller = createRecordPage(host);
  controllers.push(controller);
  return { controller, page: controller.page };
}

afterEach(() => {
  for (const controller of controllers.splice(0)) controller.leave();
});

describe("a record page's state facts", () => {
  it("reports its identity, docstatus, unsaved edits and errors", async () => {
    const { controller, page } = makePage();
    await controller.refresh();
    page.fields.setError("status", "Say why");

    expect(await acts.factsOf("record", false)).toEqual({
      doctype: "CRM Deal",
      name: "CRM-DEAL-1",
      docstatus: 1,
      unsaved: true,
      errors: { status: "Say why" },
    });
  });

  it("adds only the fields the layout shows, a table as its row count", async () => {
    const { controller } = makePage();
    await controller.refresh();

    const facts = (await acts.factsOf("record", true)) as { fields: unknown[] };

    expect(facts.fields).toEqual([
      { label: "Status", fieldname: "status", type: "Select", value: "Open", required: true, read_only: false },
      { label: "products", fieldname: "products", type: "Table", value: "2 rows", required: false, read_only: false },
    ]);
  });
});
