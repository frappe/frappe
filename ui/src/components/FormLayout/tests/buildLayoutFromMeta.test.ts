import { describe, expect, it } from "vitest";
import { buildLayoutFromMeta, compose } from "../buildLayoutFromMeta";
import type { RawMetaField } from "../types";

const field = (over: Partial<RawMetaField>): RawMetaField => ({
  fieldname: "f",
  fieldtype: "Data",
  ...over,
});

describe("buildLayoutFromMeta", () => {
  it("returns an empty schema for no fields", () => {
    expect(buildLayoutFromMeta([])).toEqual([]);
  });

  it("seeds one implicit tab/section/column for a flat list with no breaks", () => {
    const layout = buildLayoutFromMeta([
      field({ fieldname: "a" }),
      field({ fieldname: "b" }),
    ]);

    expect(layout).toHaveLength(1);
    expect(layout[0].sections).toHaveLength(1);
    expect(layout[0].sections[0].columns).toHaveLength(1);
    expect(
      layout[0].sections[0].columns[0].fields.map((f) => f.fieldname)
    ).toEqual(["a", "b"]);
  });

  it("a leading field before any break lands in the seeded container", () => {
    const layout = buildLayoutFromMeta([
      field({ fieldname: "lead" }),
      field({ fieldname: "tab", fieldtype: "Tab Break", label: "Tab 2" }),
      field({ fieldname: "after" }),
    ]);

    expect(layout).toHaveLength(2);
    expect(
      layout[0].sections[0].columns[0].fields.map((f) => f.fieldname)
    ).toEqual(["lead"]);
    expect(layout[1].label).toBe("Tab 2");
    expect(
      layout[1].sections[0].columns[0].fields.map((f) => f.fieldname)
    ).toEqual(["after"]);
  });

  it("nests Tab / Section / Column breaks correctly", () => {
    const layout = buildLayoutFromMeta([
      field({ fieldname: "s1", fieldtype: "Section Break", label: "S1" }),
      field({ fieldname: "a" }),
      field({ fieldname: "c1", fieldtype: "Column Break" }),
      field({ fieldname: "b" }),
      field({ fieldname: "t2", fieldtype: "Tab Break", label: "Tab 2" }),
      field({ fieldname: "s2", fieldtype: "Section Break", label: "S2" }),
      field({ fieldname: "c" }),
    ]);

    expect(layout).toHaveLength(2);

    // Tab 1: section S1 with two columns (a | b)
    const tab1 = layout[0];
    expect(tab1.sections).toHaveLength(1);
    expect(tab1.sections[0].label).toBe("S1");
    expect(tab1.sections[0].columns).toHaveLength(2);
    expect(tab1.sections[0].columns[0].fields.map((f) => f.fieldname)).toEqual([
      "a",
    ]);
    expect(tab1.sections[0].columns[1].fields.map((f) => f.fieldname)).toEqual([
      "b",
    ]);

    // Tab 2: section S2 with one column (c)
    const tab2 = layout[1];
    expect(tab2.label).toBe("Tab 2");
    expect(tab2.sections[0].label).toBe("S2");
    expect(tab2.sections[0].columns[0].fields.map((f) => f.fieldname)).toEqual([
      "c",
    ]);
  });

  it("maps section-break attributes (hideBorder, collapsible, opened)", () => {
    const layout = buildLayoutFromMeta([
      field({
        fieldname: "s",
        fieldtype: "Section Break",
        label: "More",
        hide_border: 1,
        collapsible: 1,
      }),
      field({ fieldname: "a" }),
    ]);

    const section = layout[0].sections[0];
    expect(section.label).toBe("More");
    expect(section.hideBorder).toBe(true);
    expect(section.collapsible).toBe(true);
    // collapsible sections start collapsed
    expect(section.opened).toBe(false);
  });

  it("keeps statically hidden fields in the schema, marked hidden", () => {
    // Hidden data fields stay in the schema (filtered out at render time) so
    // meta-script ops can target them; only layout breaks are dropped.
    const layout = buildLayoutFromMeta([
      field({ fieldname: "visible" }),
      field({ fieldname: "secret", hidden: 1 }),
    ]);

    const fields = layout[0].sections[0].columns[0].fields;
    expect(fields.map((f) => f.fieldname)).toEqual(["visible", "secret"]);
    expect(fields.find((f) => f.fieldname === "secret")!.hidden).toBe(true);
  });

  it("maps snake_case meta to camelCase and carries depends_on through as a string", () => {
    const layout = buildLayoutFromMeta([
      field({
        fieldname: "owner",
        fieldtype: "Link",
        label: "Owner",
        options: "User",
        reqd: 1,
        depends_on: 'eval:doc.status == "Open"',
        mandatory_depends_on: 'eval:doc.priority == "High"',
        read_only_depends_on: "eval:doc.locked",
      }),
    ]);

    const f = layout[0].sections[0].columns[0].fields[0];
    expect(f.fieldtype).toBe("Link");
    expect(f.options).toBe("User");
    expect(f.reqd).toBe(true);
    expect(f.dependsOn).toBe('eval:doc.status == "Open"');
    expect(f.mandatoryDependsOn).toBe('eval:doc.priority == "High"');
    expect(f.readOnlyDependsOn).toBe("eval:doc.locked");
  });

  it("carries depends_on onto sections and tabs", () => {
    const layout = buildLayoutFromMeta([
      field({
        fieldname: "t2",
        fieldtype: "Tab Break",
        label: "Tab 2",
        depends_on: "eval:doc.show_tab",
      }),
      field({
        fieldname: "s",
        fieldtype: "Section Break",
        label: "S",
        depends_on: "eval:doc.show_section",
      }),
      field({ fieldname: "a" }),
    ]);

    expect(layout[0].dependsOn).toBe("eval:doc.show_tab");
    expect(layout[0].sections[0].dependsOn).toBe("eval:doc.show_section");
  });

  it("maps static read_only to readOnly", () => {
    const layout = buildLayoutFromMeta([
      field({ fieldname: "a", read_only: 1 }),
    ]);
    expect(layout[0].sections[0].columns[0].fields[0].readOnly).toBe(true);
  });

  it("treats the Read Only fieldtype as readOnly", () => {
    const layout = buildLayoutFromMeta([
      field({ fieldname: "ro", fieldtype: "Read Only" }),
    ]);
    expect(layout[0].sections[0].columns[0].fields[0].readOnly).toBe(true);
  });

  describe("Table child columns", () => {
    const tableField = (over: Partial<RawMetaField> = {}) =>
      field({
        fieldname: "items",
        fieldtype: "Table",
        options: "Order Item",
        ...over,
      });

    const tableFieldOf = (layout: ReturnType<typeof buildLayoutFromMeta>) =>
      layout[0].sections[0].columns[0].fields[0];

    it("resolves child columns from in_list_view fields of the child meta", () => {
      const layout = buildLayoutFromMeta([tableField()], {
        childMetas: {
          "Order Item": [
            field({
              fieldname: "item",
              fieldtype: "Link",
              options: "Item",
              in_list_view: 1,
            }),
            field({ fieldname: "note", fieldtype: "Data" }), // not in_list_view → excluded
            field({ fieldname: "qty", fieldtype: "Int", in_list_view: 1 }),
          ],
        },
      });

      const f = tableFieldOf(layout);
      expect(f.childFields?.map((c) => c.fieldname)).toEqual(["item", "qty"]);
      // columns are mapped through the same FieldMeta shape
      expect(f.childFields?.[0].options).toBe("Item");
    });

    it("falls back to all visible data fields when none are flagged in_list_view", () => {
      const layout = buildLayoutFromMeta([tableField()], {
        childMetas: {
          "Order Item": [
            field({ fieldname: "sec", fieldtype: "Section Break" }), // layout break → excluded
            field({ fieldname: "item", fieldtype: "Data" }),
            field({ fieldname: "secret", fieldtype: "Data", hidden: 1 }), // hidden → excluded
            field({ fieldname: "qty", fieldtype: "Int" }),
          ],
        },
      });

      expect(tableFieldOf(layout).childFields?.map((c) => c.fieldname)).toEqual(
        ["item", "qty"]
      );
    });

    it("leaves childFields undefined when the child meta is absent", () => {
      const layout = buildLayoutFromMeta([tableField()], { childMetas: {} });
      expect(tableFieldOf(layout).childFields).toBeUndefined();
    });

    it("does not attach childFields to non-Table fields", () => {
      const layout = buildLayoutFromMeta([
        field({ fieldname: "a", fieldtype: "Data" }),
      ]);
      expect(tableFieldOf(layout).childFields).toBeUndefined();
    });

    it("attaches the full child layout (all fields + child breaks) as childLayout", () => {
      const layout = buildLayoutFromMeta([tableField()], {
        childMetas: {
          "Order Item": [
            field({
              fieldname: "item",
              fieldtype: "Link",
              options: "Item",
              in_list_view: 1,
            }),
            field({ fieldname: "details", fieldtype: "Section Break" }),
            field({ fieldname: "note", fieldtype: "Data" }), // not a grid column…
            field({ fieldname: "qty", fieldtype: "Int", in_list_view: 1 }),
          ],
        },
      });

      const f = tableFieldOf(layout);
      // grid columns stay the in_list_view subset
      expect(f.childFields?.map((c) => c.fieldname)).toEqual(["item", "qty"]);
      // …but the dialog layout carries every field, in the child's own sections
      const sections = f.childLayout?.[0].sections ?? [];
      const allFields = sections.flatMap((s) =>
        s.columns.flatMap((c) => c.fields.map((cf) => cf.fieldname))
      );
      expect(allFields).toEqual(["item", "note", "qty"]);
      expect(sections.length).toBe(2); // split on the child's Section Break
    });

    it("leaves childLayout undefined when the child meta is absent", () => {
      const layout = buildLayoutFromMeta([tableField()], { childMetas: {} });
      expect(tableFieldOf(layout).childLayout).toBeUndefined();
    });

    it("does not attach childLayout to Table MultiSelect (it has no row dialog)", () => {
      const layout = buildLayoutFromMeta(
        [
          field({
            fieldname: "roles",
            fieldtype: "Table MultiSelect",
            options: "Has Role",
          }),
        ],
        {
          childMetas: {
            "Has Role": [
              field({ fieldname: "role", fieldtype: "Link", options: "Role" }),
            ],
          },
        }
      );
      expect(tableFieldOf(layout).childLayout).toBeUndefined();
    });

    it("resolves childFields for Table MultiSelect (its single Link field)", () => {
      const layout = buildLayoutFromMeta(
        [
          field({
            fieldname: "roles",
            fieldtype: "Table MultiSelect",
            options: "Has Role",
          }),
        ],
        {
          childMetas: {
            "Has Role": [
              field({
                fieldname: "role",
                fieldtype: "Link",
                options: "Role",
                in_list_view: 1,
              }),
            ],
          },
        }
      );

      const f = tableFieldOf(layout);
      expect(f.childFields?.map((c) => c.fieldname)).toEqual(["role"]);
      // the link field's target doctype is what the picker searches against
      expect(f.childFields?.[0].options).toBe("Role");
    });
  });

  describe("decorate hook", () => {
    const onClick = () => {};

    it("overlays the returned ui on the matching node and leaves others plain", () => {
      const layout = buildLayoutFromMeta(
        [
          field({ fieldname: "send", fieldtype: "Button" }),
          field({ fieldname: "a" }),
        ],
        {
          decorate: (f) =>
            f.fieldname === "send"
              ? { props: { variant: "solid" }, on: { click: onClick } }
              : undefined,
        }
      );

      const [send, a] = layout[0].sections[0].columns[0].fields;
      expect(send.ui).toEqual({
        props: { variant: "solid" },
        on: { click: onClick },
      });
      // a node the hook ignores stays a plain FieldMeta with no `ui` key.
      expect(a.ui).toBeUndefined();
      expect("ui" in a).toBe(false);
    });

    it("receives the resolved meta and can key off fieldtype", () => {
      const seen: string[] = [];
      buildLayoutFromMeta([field({ fieldname: "x", fieldtype: "Int" })], {
        decorate: (f) => {
          seen.push(`${f.fieldname}:${f.fieldtype}`);
        },
      });
      expect(seen).toEqual(["x:Int"]);
    });

    it("runs for grid columns too (childFields carry ui)", () => {
      const layout = buildLayoutFromMeta(
        [
          field({
            fieldname: "items",
            fieldtype: "Table",
            options: "Order Item",
          }),
        ],
        {
          childMetas: {
            "Order Item": [
              field({ fieldname: "qty", fieldtype: "Int", in_list_view: 1 }),
              field({
                fieldname: "remove",
                fieldtype: "Button",
                in_list_view: 1,
              }),
            ],
          },
          decorate: (f) =>
            f.fieldname === "remove" ? { props: { theme: "red" } } : undefined,
        }
      );

      const cols = layout[0].sections[0].columns[0].fields[0].childFields ?? [];
      expect(cols.find((c) => c.fieldname === "remove")?.ui).toEqual({
        props: { theme: "red" },
      });
      expect(cols.find((c) => c.fieldname === "qty")?.ui).toBeUndefined();
    });
  });

  describe("compose", () => {
    it("merges props (shallow) and last-wins component, concatenating on handlers", () => {
      const style = () => ({ props: { variant: "solid" } });
      const click = () => {};
      const scriptChange = () => {};
      const styleChange = () => {};
      const behaviour = () => ({
        props: { theme: "blue" },
        on: { change: scriptChange, click },
      });
      const more = () => ({ on: { change: styleChange } });

      const decorate = compose(style, behaviour, more);
      const ui = decorate(field({ fieldname: "f" }) as any);

      expect(ui?.props).toEqual({ variant: "solid", theme: "blue" });
      // two `change` contributors → array of both, so every handler fires.
      expect(ui?.on?.change).toEqual([scriptChange, styleChange]);
      // a single contributor stays a bare function (not wrapped in an array).
      expect(ui?.on?.click).toBe(click);
    });

    it("returns undefined when every decorator opts out", () => {
      const decorate = compose(
        () => undefined,
        () => {}
      );
      expect(decorate(field({ fieldname: "f" }))).toBeUndefined();
    });
  });
});
