import { beforeEach, describe, expect, it, vi } from "vitest";
import type { RawMetaField } from "../../FormLayout/types";

// useListView builds useQuickFilter + useColumns, which read doctype Meta (via
// useDoctypeMeta → frappe-ui, unresolvable in unit tests), so mock that composable
// with a reactive ref we drive directly — the same pattern as useQuickFilter's test.
const h = vi.hoisted(() => ({ meta: null as any }));
vi.mock("../../../composables/useDoctypeMeta", async () => {
  const { ref } = await import("vue");
  h.meta = ref(null);
  return { useDoctypeMeta: () => ({ meta: h.meta }) };
});

import { useListView } from "../useListView";
import type { ListViewSnapshot } from "../useListView";
import type { FilterCondition, FilterField } from "../../Filter/types";
import type { Sort } from "../../SortBy/types";
import type { Column } from "../../ColumnSettings/types";

const FIELDS: RawMetaField[] = [
  {
    fieldname: "status",
    fieldtype: "Select",
    label: "Status",
    in_list_view: 1,
    in_standard_filter: 1,
  },
  {
    fieldname: "customer",
    fieldtype: "Link",
    label: "Customer",
    options: "Customer",
    in_list_view: 1,
    in_standard_filter: 1,
  },
  { fieldname: "notes", fieldtype: "Text", label: "Notes" },
];

const STATUS: FilterField = {
  label: "Status",
  value: "status",
  fieldname: "status",
  fieldtype: "Select",
  options: "Open\nClosed",
};

beforeEach(() => {
  h.meta.value = { name: "Sales Order", fields: FIELDS };
});

describe("useListView snapshot / restore", () => {
  it("snapshot captures the effective state of every control", () => {
    const view = useListView("Sales Order");
    const condition: FilterCondition = {
      field: STATUS,
      fieldname: "status",
      operator: "equals",
      value: "Open",
    };
    view.filters.conditions.value = [condition];
    view.sort.by.value = [{ fieldname: "modified", direction: "desc" }];

    const snapshot = view.snapshot.value;
    expect(snapshot.filters).toEqual([condition]);
    expect(snapshot.sort).toEqual([
      { fieldname: "modified", direction: "desc" },
    ]);
    // Columns / quick-filter fields fall back to the Meta-derived defaults when
    // the user hasn't customized them.
    expect(snapshot.columns.map((c) => c.fieldname)).toContain("status");
    expect(snapshot.quickFilterFields.map((f) => f.fieldname)).toContain(
      "status"
    );
  });

  it("restore seeds every control from one snapshot", () => {
    const view = useListView("Sales Order");
    const snapshot: ListViewSnapshot = {
      filters: [
        {
          field: STATUS,
          fieldname: "status",
          operator: "equals",
          value: "Won",
        },
      ],
      sort: [{ fieldname: "creation", direction: "asc" }] as Sort[],
      columns: [
        { fieldname: "customer", label: "Account", width: "200px" },
      ] as Column[],
      quickFilterFields: [STATUS],
    };

    view.restore(snapshot);

    expect(view.filters.conditions.value).toEqual(snapshot.filters);
    expect(view.sort.by.value).toEqual(snapshot.sort);
    expect(view.columns.shown.value).toEqual(snapshot.columns);
    expect(view.quickFilter.fields.value).toEqual(snapshot.quickFilterFields);
    // A restored column counts as a customization, so Reset becomes available.
    expect(view.columns.isCustomized.value).toBe(true);
  });

  it("a partial snapshot applies only the members present", () => {
    const view = useListView("Sales Order");
    const defaultColumns = view.columns.shown.value;

    view.restore({ sort: [{ fieldname: "name", direction: "asc" }] });

    expect(view.sort.by.value).toEqual([
      { fieldname: "name", direction: "asc" },
    ]);
    // Untouched: filters stay empty, columns stay at the Meta default (not customized).
    expect(view.filters.conditions.value).toEqual([]);
    expect(view.columns.shown.value).toEqual(defaultColumns);
    expect(view.columns.isCustomized.value).toBe(false);
  });

  it("threads synthetic column declarations through to useColumns (ADR-0033)", () => {
    const indicator = {
      key: "_indicator",
      label: "Status",
      type: "Status",
      place: "after-title" as const,
      subsumes: "status",
    };
    const view = useListView("Sales Order", { synthetic: [indicator] });
    // Folded into the default shown at its anchor, `status` subsumed out of the seed.
    expect(view.columns.shown.value.map((c) => c.fieldname)).toEqual([
      "name",
      "_indicator",
      "customer",
    ]);
    // And exposed so the host can bind ColumnSettings' picker union from one place.
    expect(view.columns.synthetic.value).toEqual([indicator]);
  });

  it("round-trips: a captured snapshot restores to the same effective state", () => {
    const source = useListView("Sales Order");
    source.filters.conditions.value = [
      { field: STATUS, fieldname: "status", operator: "equals", value: "Open" },
    ];
    source.sort.by.value = [{ fieldname: "modified", direction: "desc" }];
    source.columns.shown.value = [
      { fieldname: "status", label: "Status", width: "150px" },
    ];
    source.quickFilter.fields.value = [STATUS];

    // Through a JSON round-trip, as a host persisting to a backend would.
    const persisted = JSON.parse(JSON.stringify(source.snapshot.value));
    const restored = useListView("Sales Order");
    restored.restore(persisted);

    expect(restored.snapshot.value).toEqual(source.snapshot.value);
  });
});
