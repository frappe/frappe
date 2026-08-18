import { describe, expect, it } from "vitest";
import { resolveFieldConditionals, resolveLayout } from "../resolveLayout";
import type { FieldMeta, FieldNode, FormLayoutSchema } from "../types";

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

describe("resolveFieldConditionals — the `override` carrier", () => {
  const hiddenByCondition: FieldNode = {
    fieldname: "discount",
    fieldtype: "Currency",
    dependsOn: "eval:doc.has_discount",
  };

  it("passes a field through untouched when it carries no override", () => {
    const resolved = resolveFieldConditionals(hiddenByCondition, {
      has_discount: 0,
    });
    expect(resolved.hidden).toBe(true);
    expect(resolved.reqd).toBe(false);
  });

  it("beats depends_on — the one override that is not restrictive", () => {
    // `depends_on` says hide; the override says show, and wins. Nothing else in
    // this pipeline can turn a conditional result off.
    const resolved = resolveFieldConditionals(
      { ...hiddenByCondition, override: { hidden: false } },
      { has_discount: 0 }
    );
    expect(resolved.hidden).toBe(false);
  });

  it("beats depends_on in the other direction too", () => {
    const resolved = resolveFieldConditionals(
      { ...hiddenByCondition, override: { hidden: true } },
      { has_discount: 1 }
    );
    expect(resolved.hidden).toBe(true);
  });

  it("overrides reqd and readOnly independently", () => {
    const field: FieldNode = {
      fieldname: "rate",
      fieldtype: "Currency",
      reqd: true,
      readOnly: true,
    };
    const resolved = resolveFieldConditionals(
      { ...field, override: { reqd: false, readOnly: false } },
      {}
    );
    expect(resolved.reqd).toBe(false);
    expect(resolved.readOnly).toBe(false);
  });

  it("leaves a key alone when the override omits it", () => {
    const resolved = resolveFieldConditionals(
      {
        fieldname: "rate",
        fieldtype: "Currency",
        reqd: true,
        override: { hidden: true },
      } as FieldNode,
      {}
    );
    expect(resolved.hidden).toBe(true);
    expect(resolved.reqd).toBe(true);
  });

  it("refuses to lift a permlevel denial — hidden", () => {
    // `withAccess` writes the denial as a static `hidden` *and* stamps
    // `permDenied`; the stamp is what makes it a floor rather than a
    // meta-hidden field.
    const denied: FieldNode = {
      fieldname: "salary",
      fieldtype: "Currency",
      hidden: true,
      permlevel: 1,
      permDenied: true,
    };
    const resolved = resolveFieldConditionals(
      { ...denied, override: { hidden: false } },
      {}
    );
    expect(resolved.hidden).toBe(true);
  });

  it("refuses to lift a permlevel denial — readOnly", () => {
    const readAccess: FieldNode = {
      fieldname: "salary",
      fieldtype: "Currency",
      readOnly: true,
      permlevel: 1,
      permDenied: true,
    };
    const resolved = resolveFieldConditionals(
      { ...readAccess, override: { readOnly: false } },
      {}
    );
    expect(resolved.readOnly).toBe(true);
  });

  it("still lets a script hide a permlevel field — the floor is one-way", () => {
    const allowed: FieldNode = {
      fieldname: "salary",
      fieldtype: "Currency",
      permlevel: 1,
      permDenied: true,
    };
    const resolved = resolveFieldConditionals(
      { ...allowed, override: { hidden: true } },
      {}
    );
    expect(resolved.hidden).toBe(true);
  });

  it("un-hides a plain meta-hidden field — permlevel 0 is not a floor", () => {
    const metaHidden: FieldNode = {
      fieldname: "internal_note",
      fieldtype: "Small Text",
      hidden: true,
    };
    const resolved = resolveFieldConditionals(
      { ...metaHidden, override: { hidden: false } },
      {}
    );
    expect(resolved.hidden).toBe(false);
  });

  it("does not mutate the input field (purity)", () => {
    const field: FieldNode = {
      fieldname: "discount",
      fieldtype: "Currency",
      override: { hidden: false },
      dependsOn: "eval:doc.has_discount",
    };
    const before = JSON.parse(JSON.stringify(field));
    resolveFieldConditionals(field, { has_discount: 0 });
    expect(field).toEqual(before);
  });

  it("carries the override through a whole-schema resolve", () => {
    const layout: FormLayoutSchema = [
      {
        name: "t",
        sections: [
          {
            name: "s",
            columns: [{ name: "c", fields: [{ ...hiddenByCondition, override: { hidden: false } }] }],
          },
        ],
      },
    ];
    const [tab] = resolveLayout(layout, { has_discount: 0 });
    expect(tab.sections[0].columns[0].fields[0].hidden).toBe(false);
  });
});

describe("the permlevel floor is the denial, not the level", () => {
  // The distinction the whole floor rests on: `withAccess` leaves a field
  // untouched when the reader *has* the level, so `permlevel` alone says
  // nothing about whether this reader was denied.

  it("lets an override un-hide a meta-hidden field the reader may write", () => {
    // permlevel 1, but not denied — the reader has the level. The field is
    // hidden because the *meta* hides it, which is overridable.
    const field: FieldNode = {
      fieldname: "salary",
      fieldtype: "Currency",
      hidden: true,
      permlevel: 1,
      override: { hidden: false },
    };
    expect(resolveFieldConditionals(field, {}).hidden).toBe(false);
  });

  it("lets an override un-lock a `Read Only` fieldtype carrying a permlevel", () => {
    // `mapField` marks the `Read Only` *fieldtype* readOnly. That is not a
    // permission decision, so a permlevel on the same field must not freeze it.
    const field: FieldNode = {
      fieldname: "code",
      fieldtype: "Read Only",
      readOnly: true,
      permlevel: 2,
      override: { readOnly: false },
    };
    expect(resolveFieldConditionals(field, {}).readOnly).toBe(false);
  });

  it("floors nothing on a layout built without a permission gate", () => {
    // `buildLayoutFromMeta` never applies `withAccess`, so nothing it produces
    // is stamped and every override on that path applies.
    const field: FieldNode = {
      fieldname: "salary",
      fieldtype: "Currency",
      hidden: true,
      permlevel: 3,
      override: { hidden: false },
    };
    expect(resolveFieldConditionals(field, {}).hidden).toBe(false);
  });

  it("refuses reqd on a field the reader was denied write access to", () => {
    // Demanding a field the reader cannot fill is a form that never submits.
    const denied: FieldNode = {
      fieldname: "salary",
      fieldtype: "Currency",
      readOnly: true,
      permlevel: 1,
      permDenied: true,
      override: { reqd: true },
    };
    expect(resolveFieldConditionals(denied, {}).reqd).toBe(false);
  });

  it("still lets an override make a writable field mandatory", () => {
    const field: FieldNode = {
      fieldname: "rate",
      fieldtype: "Currency",
      override: { reqd: true },
    };
    expect(resolveFieldConditionals(field, {}).reqd).toBe(true);
  });

  it("a hidden denial does not floor readOnly, and vice versa", () => {
    // A `none` denial sets `hidden` and says nothing about writability.
    const hiddenDenial: FieldNode = {
      fieldname: "salary",
      fieldtype: "Currency",
      hidden: true,
      readOnly: true,
      permlevel: 1,
      permDenied: true,
      override: { hidden: false, readOnly: false },
    };
    const resolved = resolveFieldConditionals(hiddenDenial, {});
    expect(resolved.hidden).toBe(true);
    expect(resolved.readOnly).toBe(true);
  });
});
