import { beforeEach, describe, expect, it, vi } from "vitest";
import type { RawMetaField } from "../../FormLayout/types";

// useQuickFilter reads doctype Meta (via useDoctypeMeta → frappe-ui, unresolvable
// in unit tests), so mock that composable with a reactive ref we drive directly.
// The factory replaces the module, so the real frappe-ui import is never loaded.
const h = vi.hoisted(() => ({ meta: null as any }));
vi.mock("../../../composables/useDoctypeMeta", async () => {
  const { ref } = await import("vue");
  h.meta = ref(null);
  return { useDoctypeMeta: () => ({ meta: h.meta }) };
});

import { useQuickFilter } from "../useQuickFilter";

const FIELDS: RawMetaField[] = [
  {
    fieldname: "status",
    fieldtype: "Select",
    label: "Status",
    in_standard_filter: 1,
  },
  {
    fieldname: "priority",
    fieldtype: "Select",
    label: "Priority",
    in_standard_filter: 1,
  },
  { fieldname: "notes", fieldtype: "Text", label: "Notes" },
];

function setMeta(fields: RawMetaField[]) {
  h.meta.value = { name: "Test DT", fields };
}

beforeEach(() => {
  h.meta.value = null;
});

describe("useQuickFilter", () => {
  it("defaults to a leading Name field plus the in_standard_filter fields", () => {
    setMeta(FIELDS);
    const { fields, customizing } = useQuickFilter("Test DT");
    expect(fields.value.map((f) => f.fieldname)).toEqual([
      "name",
      "status",
      "priority",
    ]);
    expect(customizing.value).toBe(false);
  });

  it("surfaces the Name field as a self-Link against the doctype", () => {
    setMeta(FIELDS);
    const { fields } = useQuickFilter("Test DT");
    expect(fields.value[0]).toMatchObject({
      fieldname: "name",
      fieldtype: "Link",
      options: "Test DT",
    });
  });

  it("a custom fields write sticks over the Meta default", () => {
    setMeta(FIELDS);
    const { fields } = useQuickFilter("Test DT");
    fields.value = [
      {
        label: "Status",
        value: "status",
        fieldname: "status",
        fieldtype: "Select",
      },
    ];
    expect(fields.value.map((f) => f.fieldname)).toEqual(["status"]);
  });

  it("canCustomize is true when the doctype offers filterable fields", () => {
    setMeta(FIELDS);
    const { canCustomize } = useQuickFilter("Test DT");
    expect(canCustomize.value).toBe(true);
  });

  it("toggles customizing independently of the surfaced fields", () => {
    setMeta(FIELDS);
    const { fields, customizing } = useQuickFilter("Test DT");
    customizing.value = true;
    expect(customizing.value).toBe(true);
    expect(fields.value.map((f) => f.fieldname)).toEqual([
      "name",
      "status",
      "priority",
    ]);
  });
});
