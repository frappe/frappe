// A script's patch on a table's column, `<table>.<column>`: the grid, the row form and the
// per-row Details layout all draw it, and `page.fields` reads it back.
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("frappe-ui", () => ({
  call: vi.fn(),
  toast: { success: vi.fn(), error: vi.fn() },
  frappeRequest: vi.fn(),
  createResource: () => ({ data: null, loading: false, fetch() {}, reload() {} }),
}));

import { layoutFields } from "@framework/ui/FormLayout";
import type { FieldNode, RawMetaField } from "@framework/ui/FormLayout/types";
import { FieldErrors } from "../fieldErrors";
import { FieldsSurface, resetFieldWarnings, type FieldsSurfaceHost } from "../fields";
import { joinLayout } from "../formLayoutSource/joinLayout";
import type { FieldPatch } from "../formLayoutSource/fieldPatch";
import type { FormLayoutRow, LayoutTree } from "../formLayoutSource/types";

const QUESTION = "Lead Form Question";
const ASSIGNEE = "Rule User";

const parentFields: RawMetaField[] = [
  { fieldname: "title", fieldtype: "Data" },
  { fieldname: "questions", fieldtype: "Table", options: QUESTION },
  { fieldname: "users", fieldtype: "Table MultiSelect", options: ASSIGNEE },
];

const questionFields: RawMetaField[] = [
  { fieldname: "label", fieldtype: "Data", label: "Question", in_list_view: 1 },
  { fieldname: "mapped_to", fieldtype: "Select", label: "Maps to", in_list_view: 1 },
  { fieldname: "note", fieldtype: "Data", label: "Note", depends_on: "eval:doc.label", in_list_view: 1 },
  { fieldname: "notes_break", fieldtype: "Section Break" },
];

const assigneeFields: RawMetaField[] = [{ fieldname: "user", fieldtype: "Link", options: "User" }];

const childMetas: Record<string, RawMetaField[]> = {
  [QUESTION]: questionFields,
  [ASSIGNEE]: assigneeFields,
};

function tree(...fields: string[]): LayoutTree {
  return [{ name: "first_tab", sections: [{ name: "main", columns: [{ fields }] }] }];
}

function table(fieldname: string, overrides: Record<string, FieldPatch>, rows?: FormLayoutRow[]) {
  const schema = joinLayout(tree("title", "questions", "users"), parentFields, {
    childMetas,
    childLayouts: rows ? { [QUESTION]: rows } : undefined,
    overrides,
  });
  return layoutFields(schema).find((field) => field.fieldname === fieldname)!;
}

const byName = (fields: FieldNode[] | undefined, fieldname: string) =>
  fields?.find((field) => field.fieldname === fieldname);

const MAPPING: Record<string, FieldPatch> = {
  "questions.mapped_to": {
    meta: { label: "Lead field", options: "first_name\nemail" },
    override: { reqd: true },
  },
};

describe("a column patch in the join", () => {
  it("reaches the grid's column and leaves the other columns alone", () => {
    const questions = table("questions", MAPPING);
    expect(byName(questions.childFields, "mapped_to")).toMatchObject({
      label: "Lead field",
      options: "first_name\nemail",
      override: { reqd: true },
    });
    expect(byName(questions.childFields, "label")).toEqual(
      byName(table("questions", {}).childFields, "label"),
    );
  });

  it("reaches the row dialog's form", () => {
    const questions = table("questions", MAPPING);
    expect(byName(layoutFields(questions.childLayout!), "mapped_to")).toMatchObject({
      label: "Lead field",
      options: "first_name\nemail",
    });
  });

  it("reaches the child's Details row the dialog picks for a row", () => {
    const row: FormLayoutRow = { name: "default", condition: null, layout: tree("label", "mapped_to") };
    const questions = table("questions", MAPPING, [row]);
    const drawn = layoutFields(questions.rowLayout!({ label: "Email?" }));
    expect(byName(drawn, "mapped_to")).toMatchObject({ label: "Lead field", options: "first_name\nemail" });
  });

  it("reaches a Table MultiSelect's link column", () => {
    const users = table("users", {
      "users.user": { meta: { filters: { enabled: 1 } } },
    });
    expect(byName(users.childFields, "user")?.filters).toEqual({ enabled: 1 });
  });

  it("keeps the table's own patch beside its columns'", () => {
    const questions = table("questions", { ...MAPPING, questions: { meta: { label: "Mapping" } } });
    expect(questions.label).toBe("Mapping");
    expect(byName(questions.childFields, "mapped_to")?.label).toBe("Lead field");
  });

  it("leaves a second table of the same child doctype alone", () => {
    const fields = [...parentFields, { fieldname: "old_questions", fieldtype: "Table", options: QUESTION }];
    const schema = joinLayout(tree("questions", "old_questions"), fields, { childMetas, overrides: MAPPING });
    const old = layoutFields(schema).find((field) => field.fieldname === "old_questions")!;
    expect(byName(old.childFields, "mapped_to")?.label).toBe("Maps to");
    expect(byName(layoutFields(old.childLayout!), "mapped_to")?.label).toBe("Maps to");
  });

  it("matches the table by its whole name", () => {
    const questions = table("questions", { "questions_old.mapped_to": { meta: { label: "x" } } });
    expect(byName(questions.childFields, "mapped_to")?.label).toBe("Maps to");
  });
});

function makeSurface(
  childFields: FieldsSurfaceHost["childFields"] = (doctype) => childMetas[doctype],
) {
  return new FieldsSurface({
    fields: () => parentFields,
    doc: () => ({}),
    fieldAccess: () => "write",
    errors: new FieldErrors(),
    childFields,
  });
}

beforeEach(() => {
  resetFieldWarnings();
  vi.restoreAllMocks();
});

describe("page.fields on a column", () => {
  it("records an update under the column's name, in the pipeline's vocabulary", () => {
    const fields = makeSurface();
    fields.update("questions.mapped_to", { options: "first_name\nemail", label: "Lead field", reqd: 1 });
    expect(fields.resolve()["questions.mapped_to"]).toEqual(MAPPING["questions.mapped_to"]);
  });

  it("hides and shows a column", () => {
    const fields = makeSurface();
    fields.hide("questions.note");
    expect(fields.get("questions.note")?.hidden).toBe(true);
    fields.show("questions.note");
    expect(fields.resolve()["questions.note"]).toEqual({ override: { hidden: false } });
  });

  it("reads a column back as the overlay leaves it, with no row's `depends_on`", () => {
    const fields = makeSurface();
    expect(fields.get("questions.note")).toMatchObject({ fieldname: "note", hidden: false });
    fields.update("questions.mapped_to", { options: "first_name\nemail" });
    expect(fields.get("questions.mapped_to")).toMatchObject({ options: "first_name\nemail" });
  });

  it("knows a table's columns, and nothing under a field that holds no rows", () => {
    const fields = makeSurface();
    expect(fields.has("questions.mapped_to")).toBe(true);
    expect(fields.has("users.user")).toBe(true);
    expect(fields.has("questions.notes_break")).toBe(false);
    expect(fields.has("title.mapped_to")).toBe(false);
  });

  it("warns on a column the child doctype lacks, once its meta is in", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    makeSurface(() => undefined).update("questions.nope", { label: "x" });
    expect(warn).not.toHaveBeenCalled();
    makeSurface().update("questions.nope", { label: "x" });
    expect(warn).toHaveBeenCalledWith(
      '[record-page] page.fields.update("questions.nope") — no such table column.',
    );
  });

  it("refuses a column's error, which belongs to a row", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const errors = new FieldErrors();
    const fields = new FieldsSurface({
      fields: () => parentFields,
      doc: () => ({}),
      fieldAccess: () => "write",
      errors,
      childFields: (doctype) => childMetas[doctype],
    });
    const error = fields.setError("questions.mapped_to", "Pick a field");
    expect(error.message).toBe("Pick a field");
    expect(errors.drawn.value).toEqual({});
    expect(warn).toHaveBeenCalledWith(
      '[record-page] page.fields.setError("questions.mapped_to") — a table column; row.setError in its row handler is the verb.',
    );
  });
});
