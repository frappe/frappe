import { describe, expect, it } from "vitest";
import { resolveFieldConditionals, resolveLayout } from "../resolveLayout";
import type { FieldMeta, FormLayoutSchema } from "../types";

const schema: FormLayoutSchema = [
  {
    name: "main",
    label: "Main",
    dependsOn: "eval:doc.show_tab",
    sections: [
      {
        name: "sec",
        label: "Section",
        dependsOn: "eval:doc.show_section",
        columns: [
          {
            name: "col",
            fields: [
              {
                fieldname: "a",
                fieldtype: "Data",
                dependsOn: "eval:doc.show_a",
              },
              {
                fieldname: "b",
                fieldtype: "Data",
                mandatoryDependsOn: "eval:doc.need_b",
              },
              {
                fieldname: "c",
                fieldtype: "Data",
                readOnlyDependsOn: "eval:doc.lock_c",
              },
            ],
          },
        ],
      },
    ],
  },
];

const fieldByName = (layout: FormLayoutSchema, name: string) =>
  layout[0].sections[0].columns[0].fields.find((f) => f.fieldname === name)!;

describe("resolveLayout", () => {
  it("hides a field when its depends_on is false and shows it when true", () => {
    expect(
      fieldByName(resolveLayout(schema, { show_a: true }), "a").hidden
    ).toBe(false);
    expect(
      fieldByName(resolveLayout(schema, { show_a: false }), "a").hidden
    ).toBe(true);
  });

  it("hides a section when its depends_on is false", () => {
    expect(
      resolveLayout(schema, { show_section: true })[0].sections[0].hidden
    ).toBe(false);
    expect(
      resolveLayout(schema, { show_section: false })[0].sections[0].hidden
    ).toBe(true);
  });

  it("hides a tab when its depends_on is false", () => {
    expect(resolveLayout(schema, { show_tab: true })[0].hidden).toBe(false);
    expect(resolveLayout(schema, { show_tab: false })[0].hidden).toBe(true);
  });

  it("flips reqd from mandatory_depends_on", () => {
    expect(fieldByName(resolveLayout(schema, { need_b: true }), "b").reqd).toBe(
      true
    );
    expect(
      fieldByName(resolveLayout(schema, { need_b: false }), "b").reqd
    ).toBe(false);
  });

  it("flips readOnly from read_only_depends_on", () => {
    expect(
      fieldByName(resolveLayout(schema, { lock_c: true }), "c").readOnly
    ).toBe(true);
    expect(
      fieldByName(resolveLayout(schema, { lock_c: false }), "c").readOnly
    ).toBe(false);
  });

  it("preserves a statically reqd / readOnly field regardless of conditions", () => {
    const s: FormLayoutSchema = [
      {
        sections: [
          {
            columns: [
              {
                fields: [
                  {
                    fieldname: "x",
                    fieldtype: "Data",
                    reqd: true,
                    readOnly: true,
                  },
                ],
              },
            ],
          },
        ],
      },
    ];
    const x = fieldByName(resolveLayout(s, {}), "x");
    expect(x.reqd).toBe(true);
    expect(x.readOnly).toBe(true);
  });

  it("does not mutate the input schema (purity)", () => {
    const before = JSON.parse(JSON.stringify(schema));
    resolveLayout(schema, {
      show_a: false,
      show_section: false,
      need_b: true,
      lock_c: true,
    });
    expect(schema).toEqual(before);
  });
});

describe("resolveFieldConditionals", () => {
  // The per-field resolver used by the grid cell, against a single row. Each row
  // resolves independently, so a per-row condition reads in the grid cell exactly
  // as it does in the row-edit dialog.
  const hide: FieldMeta = {
    fieldname: "a",
    fieldtype: "Data",
    dependsOn: "eval:doc.show",
  };
  const lock: FieldMeta = {
    fieldname: "b",
    fieldtype: "Data",
    readOnlyDependsOn: "eval:doc.lock",
  };
  const need: FieldMeta = {
    fieldname: "c",
    fieldtype: "Data",
    mandatoryDependsOn: "eval:doc.need",
  };

  it("resolves hidden per row from depends_on", () => {
    expect(resolveFieldConditionals(hide, { show: true }).hidden).toBe(false);
    expect(resolveFieldConditionals(hide, { show: false }).hidden).toBe(true);
  });

  it("resolves readOnly per row from read_only_depends_on", () => {
    expect(resolveFieldConditionals(lock, { lock: true }).readOnly).toBe(true);
    expect(resolveFieldConditionals(lock, { lock: false }).readOnly).toBe(
      false
    );
  });

  it("resolves reqd per row from mandatory_depends_on", () => {
    expect(resolveFieldConditionals(need, { need: true }).reqd).toBe(true);
    expect(resolveFieldConditionals(need, { need: false }).reqd).toBe(false);
  });

  it("the same field resolves differently for two rows", () => {
    expect(resolveFieldConditionals(lock, { lock: true }).readOnly).toBe(true);
    expect(resolveFieldConditionals(lock, { lock: false }).readOnly).toBe(
      false
    );
  });

  it("passes a field with no expressions through unchanged", () => {
    const plain: FieldMeta = {
      fieldname: "x",
      fieldtype: "Data",
      readOnly: true,
      reqd: true,
    };
    const out = resolveFieldConditionals(plain, {});
    expect(out.readOnly).toBe(true);
    expect(out.reqd).toBe(true);
    expect(out.hidden).toBeUndefined();
  });

  it("resolves a child field's read_only against the parent doc via parent.x", () => {
    // A row whose rate is read-only unless the parent allows editing — desk's
    // `eval:parent.allow_rate_edit`. The grid cell and row dialog both pass the
    // parent doc, so this resolves the same in both.
    const rate: FieldMeta = {
      fieldname: "rate",
      fieldtype: "Currency",
      readOnlyDependsOn: "eval:!parent.allow_rate_edit",
    };
    expect(
      resolveFieldConditionals(rate, { rate: 100 }, { allow_rate_edit: 1 })
        .readOnly
    ).toBe(false);
    expect(
      resolveFieldConditionals(rate, { rate: 100 }, { allow_rate_edit: 0 })
        .readOnly
    ).toBe(true);
  });

  it("does not mutate the input field (purity)", () => {
    const before = JSON.parse(JSON.stringify(lock));
    resolveFieldConditionals(lock, { lock: true });
    expect(lock).toEqual(before);
  });
});
