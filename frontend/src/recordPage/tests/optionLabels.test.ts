// A script's `options` for a Select or Autocomplete: a string, or values and `{ value, label }` pairs.
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
import { FieldsSurface, resetFieldWarnings } from "../fields";
import { joinLayout } from "../formLayoutSource/joinLayout";

const CHILD = "Lead Form Question";

const parentFields: RawMetaField[] = [
  { fieldname: "status", fieldtype: "Select", options: "Open\nWon" },
  { fieldname: "questions", fieldtype: "Table", options: CHILD },
];

const childFields: RawMetaField[] = [{ fieldname: "mapped_to", fieldtype: "Select", in_list_view: 1 }];

const PAIRS = [
  { value: "first_name", label: "First Name" },
  { value: "email", label: "Email" },
];

beforeEach(() => resetFieldWarnings());

function makeSurface() {
  return new FieldsSurface({
    fields: () => parentFields,
    doc: () => ({}),
    fieldAccess: () => "write",
    errors: new FieldErrors(),
    childFields: () => childFields,
  });
}

function drawn(overrides: ReturnType<FieldsSurface["resolve"]>, name: string) {
  const schema = joinLayout(
    [{ name: "first_tab", sections: [{ name: "main", columns: [{ fields: ["status", "questions"] }] }] }],
    parentFields,
    { childMetas: { [CHILD]: childFields }, overrides },
  );
  return layoutFields(schema).find((field) => field.fieldname === name)!;
}

describe("options as pairs", () => {
  it("lands the values as options and the pairs as choices", () => {
    const fields = makeSurface();
    fields.update("status", { options: PAIRS });
    expect(fields.resolve().status.meta).toEqual({ options: "first_name\nemail", choices: PAIRS });
  });

  it("labels a bare value by itself, and takes a mixed list", () => {
    const fields = makeSurface();
    fields.update("status", { options: ["Open", { value: "won", label: "Won" }, { value: "lost" }] });
    expect(fields.resolve().status.meta?.choices).toEqual([
      { value: "Open", label: "Open" },
      { value: "won", label: "Won" },
      { value: "lost", label: "lost" },
    ]);
  });

  it("leaves a plain string exactly as it was", () => {
    const fields = makeSurface();
    fields.update("status", { options: "Open\nLost" });
    expect(fields.resolve().status.meta).toEqual({ options: "Open\nLost", choices: undefined });
    expect(drawn(fields.resolve(), "status")).toMatchObject({ options: "Open\nLost" });
    expect(drawn(fields.resolve(), "status").choices).toBeUndefined();
  });

  it("is cleared by a later string", () => {
    const fields = makeSurface();
    fields.update("status", { options: PAIRS });
    fields.update("status", { options: "Open\nLost" });
    expect(drawn(fields.resolve(), "status").choices).toBeUndefined();
  });

  it("reads back as the pairs", () => {
    const fields = makeSurface();
    fields.update("status", { options: PAIRS });
    expect(fields.get("status")?.options).toEqual(PAIRS);
    fields.update("status", { options: "Open" });
    expect(fields.get("status")?.options).toBe("Open");
  });

  it("reaches a field and a table's column", () => {
    const fields = makeSurface();
    fields.update("status", { options: PAIRS });
    fields.update("questions.mapped_to", { options: PAIRS });
    const overrides = fields.resolve();
    expect(drawn(overrides, "status").choices).toEqual(PAIRS);
    const column = (list: FieldNode[] | undefined) => list?.find((one) => one.fieldname === "mapped_to");
    const questions = drawn(overrides, "questions");
    expect(column(questions.childFields)?.choices).toEqual(PAIRS);
    expect(column(layoutFields(questions.childLayout!))?.choices).toEqual(PAIRS);
    expect(fields.get("questions.mapped_to")?.options).toEqual(PAIRS);
  });

  it("drops what is no choice: no value, a newline, a repeat", () => {
    const fields = makeSurface();
    fields.update("status", {
      options: [null, undefined, { label: "x" }, { value: null }, { value: "a\nb" }, { value: 1, label: "One" }, "Open", { value: "Open", label: "Again" }, ""],
    });
    const meta = fields.resolve().status.meta;
    expect(meta?.choices).toEqual([
      { value: "1", label: "One" },
      { value: "Open", label: "Open" },
      { value: "", label: "" },
    ]);
    expect(meta?.options).toBe("1\nOpen\n");
  });

  it("warns on options that are neither, and empties them", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const fields = makeSurface();
    fields.update("status", { options: { value: "x" } as any });
    expect(fields.resolve().status.meta).toEqual({ options: "", choices: undefined });
    expect(warn).toHaveBeenCalledTimes(1);
  });
});
