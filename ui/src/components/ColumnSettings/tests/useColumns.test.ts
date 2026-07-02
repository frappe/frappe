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
});
