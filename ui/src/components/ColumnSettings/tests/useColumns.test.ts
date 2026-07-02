import { beforeEach, describe, expect, it, vi } from "vitest";
import type { RawMetaField } from "../../FormLayout/types";

// useColumns reads doctype Meta (via useDoctypeMeta → frappe-ui, unresolvable in
// unit tests), so mock that composable with a reactive ref we drive directly. The
// factory replaces the module, so the real frappe-ui import is never loaded.
const h = vi.hoisted(() => ({ meta: null as any }));
vi.mock("../../../composables/useDoctypeMeta", async () => {
  const { ref } = await import("vue");
  h.meta = ref(null);
  return { useDoctypeMeta: () => ({ meta: h.meta }) };
});

import { useColumns } from "../useColumns";

const FIELDS: RawMetaField[] = [
  {
    fieldname: "status",
    fieldtype: "Select",
    label: "Status",
    in_list_view: 1,
  },
  {
    fieldname: "amount",
    fieldtype: "Currency",
    label: "Amount",
    in_list_view: 1,
  },
  { fieldname: "notes", fieldtype: "Text", label: "Notes" },
];

function setMeta(fields: RawMetaField[], title_field?: string) {
  h.meta.value = { name: "Test DT", title_field, fields };
}

beforeEach(() => {
  h.meta.value = null;
});

describe("useColumns", () => {
  it("defaults to a leading `name` column plus the in_list_view fields", () => {
    setMeta(FIELDS);
    const { shown, isCustomized } = useColumns("Test DT");
    expect(shown.value).toEqual([
      { fieldname: "name", label: "Name" },
      { fieldname: "status", label: "Status" },
      { fieldname: "amount", label: "Amount" },
    ]);
    expect(isCustomized.value).toBe(false);
  });

  it("leads with the title_field when set and drops it from the tail", () => {
    setMeta(
      [
        {
          fieldname: "title",
          fieldtype: "Data",
          label: "Title",
          in_list_view: 1,
        },
        ...FIELDS,
      ],
      "title"
    );
    const { shown } = useColumns("Test DT");
    expect(shown.value[0]).toEqual({ fieldname: "title", label: "Title" });
    expect(shown.value.filter((c) => c.fieldname === "title")).toHaveLength(1);
  });

  it("marks customized once shown is written, and reset restores the defaults", () => {
    setMeta(FIELDS);
    const { shown, isCustomized, reset } = useColumns("Test DT");
    shown.value = [{ fieldname: "status", label: "Status" }];
    expect(isCustomized.value).toBe(true);
    expect(shown.value).toEqual([{ fieldname: "status", label: "Status" }]);
    reset();
    expect(isCustomized.value).toBe(false);
    expect(shown.value[0]).toEqual({ fieldname: "name", label: "Name" });
  });

  it("setWidth writes a column's width back into shown (the resize→settings half)", () => {
    setMeta(FIELDS);
    const { shown, setWidth, isCustomized } = useColumns("Test DT");
    setWidth("status", "12rem");
    expect(shown.value.find((c) => c.fieldname === "status")?.width).toBe(
      "12rem"
    );
    expect(isCustomized.value).toBe(true);
  });

  it("resetWidth clears a column's fixed width so it flexes again", () => {
    setMeta(FIELDS);
    const { shown, setWidth, resetWidth } = useColumns("Test DT");
    setWidth("status", "12rem");
    resetWidth("status");
    expect(
      shown.value.find((c) => c.fieldname === "status")?.width
    ).toBeUndefined();
  });

  it("wire renders the shown columns through serializeColumns", () => {
    setMeta(FIELDS);
    const { wire } = useColumns("Test DT");
    expect(wire.value.map((c) => c.key)).toEqual(["name", "status", "amount"]);
  });

  const indicator = {
    key: "_indicator",
    label: "Status",
    type: "Status",
    place: "after-title" as const,
    subsumes: "status",
  };

  it("folds a synthetic declaration into the default shown at its place anchor", () => {
    setMeta(FIELDS);
    const { shown } = useColumns("Test DT", { synthetic: [indicator] });
    // after-title → right after `name`; `subsumes: status` drops the status field.
    expect(shown.value.map((c) => c.fieldname)).toEqual([
      "name",
      "_indicator",
      "amount",
    ]);
  });

  it("wires a synthetic column's render metadata from the declaration (type Status)", () => {
    setMeta(FIELDS);
    const { wire } = useColumns("Test DT", { synthetic: [indicator] });
    expect(wire.value.find((c) => c.key === "_indicator")?.type).toBe("Status");
  });

  it("exposes the declarations so the host can bind ColumnSettings' picker union", () => {
    setMeta(FIELDS);
    const { synthetic } = useColumns("Test DT", { synthetic: [indicator] });
    expect(synthetic.value).toEqual([indicator]);
  });

  it("folds in a declaration that resolves asynchronously (a ref source)", async () => {
    const { ref } = await import("vue");
    setMeta(FIELDS);
    // The indicator rides a live field-meta fetch, so it is empty at first and arrives later.
    const source = ref<any[]>([]);
    const { shown } = useColumns("Test DT", { synthetic: source });
    expect(shown.value.map((c) => c.fieldname)).toEqual([
      "name",
      "status",
      "amount",
    ]);
    source.value = [indicator];
    expect(shown.value.map((c) => c.fieldname)).toEqual([
      "name",
      "_indicator",
      "amount",
    ]);
  });

  it("scrubs an orphaned synthetic key from a customized layout when the declaration is removed", async () => {
    const { ref } = await import("vue");
    setMeta(FIELDS);
    const source = ref<any[]>([indicator]);
    const { shown } = useColumns("Test DT", { synthetic: source });
    // The user customizes while the indicator is active — `_indicator` sticks in the
    // persisted layout, ahead of the docfields.
    shown.value = [
      { fieldname: "name", label: "Name" },
      { fieldname: "_indicator", label: "Status" },
      { fieldname: "amount", label: "Amount" },
    ];
    // The declaration is later removed (the syntheticDemo toggle). The orphaned
    // `_indicator` would otherwise name no docfield and error get_list.
    source.value = [];
    expect(shown.value.map((c) => c.fieldname)).toEqual(["name", "amount"]);
    // A re-declared key simply reappears — the customized layout still carries it.
    source.value = [indicator];
    expect(shown.value.map((c) => c.fieldname)).toEqual([
      "name",
      "_indicator",
      "amount",
    ]);
  });

  it("keeps the orphaned key out of the wire columns (so get_list never requests it)", async () => {
    const { ref } = await import("vue");
    setMeta(FIELDS);
    const source = ref<any[]>([indicator]);
    const { shown, wire } = useColumns("Test DT", { synthetic: source });
    shown.value = [
      { fieldname: "name", label: "Name" },
      { fieldname: "_indicator", label: "Status" },
      { fieldname: "amount", label: "Amount" },
    ];
    source.value = [];
    expect(wire.value.map((c) => c.key)).toEqual(["name", "amount"]);
  });
});
