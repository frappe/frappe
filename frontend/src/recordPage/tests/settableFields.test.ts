import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";

vi.mock("frappe-ui", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
  frappeRequest: vi.fn(),
}));
vi.mock("@framework/ui/api", () => ({
  runMethod: vi.fn(async () => ({ data: null })),
  getMeta: vi.fn(async () => ({ data: null, children: [] })),
}));

import { createRecordPage, type RecordPageHost } from "../createRecordPage";
import { formDialogHandle, initialDoc, layoutFromFields } from "../formDialogLayout";
import { resetRegistry } from "../registry";

const GATE = "eval:doc.gate == 'open'";

// A field with no `gate` on the doc or row: a `depends_on` on it is false.
const CASES: [string, Record<string, unknown>, unknown, string | undefined][] = [
  ["a plain field", { fieldtype: "Data" }, "x", undefined],
  ["a Check, sent a boolean", { fieldtype: "Check" }, true, undefined],
  ["a hidden field", { fieldtype: "Data", hidden: 1 }, "x", "is hidden now"],
  ["a field its depends_on hides", { fieldtype: "Data", depends_on: GATE }, "x", "is hidden now"],
  ["a read-only field", { fieldtype: "Data", read_only: 1 }, "x", "is read-only"],
  ["a Read Only field", { fieldtype: "Read Only" }, "x", "is read-only"],
  ["a field its read_only_depends_on locks", { fieldtype: "Data", read_only_depends_on: "eval:!doc.gate" }, "x", "is read-only"],
  ["a field that holds no value", { fieldtype: "Button" }, "x", "holds no value"],
  ["a table", { fieldtype: "Table", options: "Cell Row" }, [], "is a table"],
];

const controllers: ReturnType<typeof createRecordPage>[] = [];

beforeEach(() => {
  resetRegistry();
  vi.spyOn(console, "warn").mockImplementation(() => {});
});

afterEach(() => {
  for (const controller of controllers.splice(0)) controller.leave();
  vi.restoreAllMocks();
});

async function attempt(run: () => Promise<unknown> | unknown, read: () => unknown) {
  const refused = await Promise.resolve()
    .then(run)
    .then(() => undefined, (error: Error) => error.message);
  return refused ? { refused } : { held: read() };
}

async function onRecord(field: Record<string, unknown>, value: unknown) {
  const target = { fieldname: "target", ...field };
  const host = {
    app: "frappe", doctype: "Deal", docname: "D-1", doc: ref({ rows: [] }), saved: ref({}),
    meta: ref({ name: "Deal", fields: [target] }),
    perms: () => ({ read: 1, write: 1 }), isDirty: () => false, activeTab: () => "details", activateTab: () => {},
    save: async () => {}, reload: async () => {}, router: {}, activityRows: () => [], scrollToActivity: async () => true,
    reloadActivity: async () => {}, fileRows: () => [], reloadFiles: async () => {}, childFields: () => [],
  } as unknown as RecordPageHost;
  const controller = createRecordPage(host);
  controllers.push(controller);
  await controller.refresh();
  return attempt(
    () => controller.page.run("record.set_values", { values: { target: value } }),
    () => host.doc.value.target,
  );
}

async function inChildRow(field: Record<string, unknown>, value: unknown) {
  const host = {
    app: "frappe", doctype: "Deal", docname: "D-1", doc: ref({ rows: [] }), saved: ref({}),
    meta: ref({ name: "Deal", fields: [{ fieldname: "rows", fieldtype: "Table", options: "Cell Row" }] }),
    perms: () => ({ read: 1, write: 1 }), isDirty: () => false, activeTab: () => "details", activateTab: () => {},
    save: async () => {}, reload: async () => {}, router: {}, activityRows: () => [], scrollToActivity: async () => true,
    reloadActivity: async () => {}, fileRows: () => [], reloadFiles: async () => {},
    childFields: () => [{ fieldname: "target", ...field }],
  } as unknown as RecordPageHost;
  const controller = createRecordPage(host);
  controllers.push(controller);
  await controller.refresh();
  return attempt(
    () => controller.page.run("record.add_child_row", { table: "rows", values: { target: value } }),
    () => host.doc.value.rows[0].target,
  );
}

function inDialog(field: Record<string, unknown>, value: unknown) {
  const layout = layoutFromFields([{ fieldname: "target", ...field }] as any);
  const draft = ref(initialDoc(layout, {}));
  const handle = formDialogHandle(() => layout, draft, { submit: () => true, close: () => {} });
  return attempt(() => handle.setValues({ target: value }), () => draft.value.target);
}

describe("which fields a caller may set", () => {
  it.each(CASES)("%s: the record, a child row and a dialog agree", async (_label, field, value, why) => {
    const answers = [await onRecord(field, value), await inChildRow(field, value), await inDialog(field, value)];

    for (const answer of answers) expect(Object.keys(answer)).toEqual(Object.keys(answers[0]));
    if (!why) {
      const held = field.fieldtype === "Check" ? 1 : value;
      expect(answers).toEqual([{ held }, { held }, { held }]);
    } else {
      const [record, child, dialog] = answers as { refused: string }[];
      expect(record.refused).toContain(`target ${why}`);
      expect(child.refused).toContain(`target ${why}`);
      expect(dialog.refused).toContain("no field target");
    }
  });
});
