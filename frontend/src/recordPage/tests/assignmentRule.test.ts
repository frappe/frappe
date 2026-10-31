// Assignment Rule's file script on the record page: what desk v1's form script did, through `page`.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";

const state = vi.hoisted(() => ({ metas: {} as Record<string, any> }));

vi.mock("frappe-ui", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
  frappeRequest: vi.fn(),
}));
vi.mock("@framework/ui/api", () => ({
  runMethod: vi.fn(async () => ({ data: null })),
  getMeta: vi.fn(async (doctype: string) => ({ data: state.metas[doctype] ?? null, children: [] })),
}));

import { resetDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { createRecordPage } from "../createRecordPage";
import { withRegisteringSource } from "@/pageEngine/context";
import { resetKeptValues } from "../keptValues";
import { registerRecordPage, resetRegistry } from "../registry";
import assignmentRule from "../../../../frappe/automation/doctype/assignment_rule/frontend/record.js";

const ASSIGNMENT_RULE_FIELDS = [
  { fieldname: "document_type", fieldtype: "Link", options: "DocType" },
  { fieldname: "rule", fieldtype: "Select", options: "Round Robin\nLoad Balancing\nBased on Field" },
  { fieldname: "field", fieldtype: "Select" },
  { fieldname: "due_date_based_on", fieldtype: "Select" },
  { fieldname: "assignment_days", fieldtype: "Table", options: "Assignment Rule Day" },
];

const CONTRACT_FIELDS = [
  { fieldname: "customer_email", fieldtype: "Data" },
  { fieldname: "reviewer", fieldtype: "Link", options: "User" },
  { fieldname: "customer", fieldtype: "Link", options: "Customer" },
  { fieldname: "party", fieldtype: "Dynamic Link", options: "party_type" },
  { fieldname: "end_date", fieldtype: "Date" },
  { fieldname: "signed_at", fieldtype: "Datetime" },
  { fieldname: "details", fieldtype: "Section Break" },
];

const controllers: ReturnType<typeof createRecordPage>[] = [];

async function openRule(
  doc: Record<string, any>,
  { perms = { read: 1, write: 1 }, isNew = false }: { perms?: Record<string, number>; isNew?: boolean } = {},
) {
  await withRegisteringSource("frappe", async () => registerRecordPage("Assignment Rule", assignmentRule));
  const controller = createRecordPage({
    app: "frappe",
    doctype: "Assignment Rule",
    docname: "Contract Review",
    doc: ref(doc),
    saved: ref({ ...doc }),
    meta: ref({ name: "Assignment Rule", fields: ASSIGNMENT_RULE_FIELDS }),
    perms: () => perms,
    isNew: () => isNew,
    isDirty: () => false,
    activeTab: () => "details",
    activateTab: () => {},
    save: async () => {},
    reload: async () => {},
    router: {} as any,
    activityRows: () => [],
    scrollToActivity: async () => true,
    reloadActivity: async () => {},
    fileRows: () => [],
    reloadFiles: async () => {},
  });
  controllers.push(controller);
  controller.header.provideBuiltins(() => [{ name: "save", label: "Save", run: () => {} }]);
  await controller.refresh();
  await vi.advanceTimersByTimeAsync(0);
  return { controller, page: controller.page };
}

const headerItem = (controller: ReturnType<typeof createRecordPage>, name: string) =>
  controller.header.visible().find((item) => item.name === name);

beforeEach(() => {
  resetRegistry();
  resetDoctypeMeta();
  resetKeptValues();
  state.metas = { Contract: { name: "Contract", fields: CONTRACT_FIELDS } };
  vi.spyOn(console, "warn").mockImplementation(() => {});
  vi.useFakeTimers();
});

afterEach(() => {
  for (const controller of controllers.splice(0)) controller.leave();
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("Assignment Rule's record page", () => {
  it("offers the target doctype's user fields for `field`, and its dates for `due_date_based_on`", async () => {
    const { page } = await openRule({ document_type: "Contract", rule: "Based on Field" });

    expect(page.fields.get("field")?.options).toBe("owner\ncustomer_email\nreviewer\nparty");
    expect(page.fields.get("due_date_based_on")?.options).toBe("\nend_date\nsigned_at");
    expect(page.fields.get("due_date_based_on")?.hidden).toBeFalsy();
  });

  it("hides `due_date_based_on` when the target doctype has no date field", async () => {
    state.metas.Note = { name: "Note", fields: [{ fieldname: "title", fieldtype: "Data" }] };
    const { page } = await openRule({ document_type: "Note", rule: "Round Robin" });

    expect(page.fields.get("field")?.options).toBe("owner\ntitle");
    expect(page.fields.get("due_date_based_on")?.hidden).toBe(true);
  });

  it("redraws the choices and the description when the reader picks another doctype or rule", async () => {
    state.metas.Note = { name: "Note", fields: [{ fieldname: "title", fieldtype: "Data" }] };
    const { controller, page } = await openRule({ document_type: "Contract", rule: "Round Robin" });

    page.doc.document_type = "Note";
    await controller.commits.commit("document_type", "Note");
    page.doc.rule = "Based on Field";
    await controller.commits.commit("rule", "Based on Field");
    await vi.advanceTimersByTimeAsync(0);

    expect(page.fields.get("field")?.options).toBe("owner\ntitle");
    expect(page.fields.get("due_date_based_on")?.hidden).toBe(true);
    expect(page.fields.get("rule")?.description).toBe("Assign to the user set in this field");
  });

  it("keeps ToDo out of the `document_type` search", async () => {
    const { page } = await openRule({ rule: "Round Robin" });

    expect(page.fields.get("document_type")?.link_filters).toEqual({ name: ["!=", "ToDo"] });
  });

  it("describes the chosen rule", async () => {
    const { page } = await openRule({ rule: "Load Balancing" });

    expect(page.fields.get("rule")?.description).toBe("Assign to the one who has the least assignments");
  });

  it("fills the assignment days from a preset, replacing the rows there", async () => {
    const { controller, page } = await openRule({ rule: "Round Robin", assignment_days: [{ day: "Monday" }] });

    expect(headerItem(controller, "assignment_day_presets")?.label).toBe("Set days");
    await page.run("header.assignment_day_presets_weekends");
    expect(page.doc.assignment_days.map((row: any) => row.day)).toEqual(["Saturday", "Sunday"]);
    await page.run("header.assignment_day_presets_all_days");
    expect(page.doc.assignment_days).toHaveLength(7);
  });

  it("refuses the presets to a reader without write", async () => {
    const { page } = await openRule({ rule: "Round Robin" }, { perms: { read: 1, write: 0 } });

    const refused = await page.run("header.assignment_day_presets_weekdays").catch((error) => error);
    expect(refused).toMatchObject({ reason: "right" });
  });

  it("offers the presets on a new record, which has no record rights before its insert", async () => {
    const { page } = await openRule({ rule: "Round Robin" }, { perms: {}, isNew: true });

    await page.run("header.assignment_day_presets_weekdays");
    expect(page.doc.assignment_days).toHaveLength(5);
  });
});
