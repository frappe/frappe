import { describe, expect, it } from "vitest";
import { fieldsToLayout } from "../fieldsToLayout";
import type { FieldMeta } from "../types";

const field = (over: Partial<FieldMeta>): FieldMeta => ({
  fieldname: "f",
  fieldtype: "Data",
  ...over,
});

describe("fieldsToLayout", () => {
  it("wraps fields in a single tab/section/column", () => {
    const fields = [field({ fieldname: "a" }), field({ fieldname: "b" })];
    const layout = fieldsToLayout(fields);

    expect(layout).toHaveLength(1);
    expect(layout[0].sections).toHaveLength(1);
    expect(layout[0].sections[0].columns).toHaveLength(1);
    expect(layout[0].sections[0].columns[0].fields).toBe(fields);
  });

  it("gives the tab no label so the tab strip stays hidden", () => {
    const layout = fieldsToLayout([field({})]);
    expect(layout[0].label).toBeUndefined();
  });

  it("renders the section flush (no label, no border)", () => {
    const section = fieldsToLayout([field({})])[0].sections[0];
    expect(section.hideLabel).toBe(true);
    expect(section.hideBorder).toBe(true);
  });

  it("produces an empty-column layout for no fields", () => {
    const layout = fieldsToLayout([]);
    expect(layout[0].sections[0].columns[0].fields).toEqual([]);
  });
});
