import { describe, expect, it } from "vitest";
// The column-resize ↔ ColumnSettings sync contract (ADR-0006): the table's
// drag-resize and the ColumnSettings popover bind the SAME `Column[]` (the SoT
// `useListView` owns), so a width written by one surfaces through the other with
// no event plumbing. Verified here on the pure helpers — the wire columns the
// frappe-ui table renders from, and the width the popover edits — without
// mounting either component.
import {
  applyColumnWidth,
  parseColumns,
  serializeColumns,
} from "../../ColumnSettings/columns";
import type { Column } from "../../ColumnSettings/types";
import type { RawMetaField } from "../../FormLayout/types";

const FIELDS: RawMetaField[] = [
  { fieldname: "status", fieldtype: "Select", label: "Status" },
  { fieldname: "amount", fieldtype: "Currency", label: "Amount" },
];

const COLUMNS: Column[] = [
  { fieldname: "status", label: "Status", width: "10rem" },
  { fieldname: "amount", label: "Amount", width: "10rem" },
];

describe("resize ↔ ColumnSettings sync over the shared columns", () => {
  it("resize → settings: a columnWidthUpdated width lands on the matching Column", () => {
    // What the composite's handler does with a `{ key, width }` resize event.
    const next = applyColumnWidth(COLUMNS, "amount", "260px");
    expect(next.find((c) => c.fieldname === "amount")?.width).toBe("260px");
    // …and the table re-renders that column at the new width.
    expect(serializeColumns(next, FIELDS)[1].width).toBe("260px");
  });

  it("settings → resize: a width edited in the popover drives the rendered track", () => {
    // ColumnSettings writes width straight onto its `v-model` Column.
    const edited = COLUMNS.map((c) =>
      c.fieldname === "status" ? { ...c, width: "6rem" } : c
    );
    expect(serializeColumns(edited, FIELDS)[0].width).toBe("6rem");
  });

  it("a resized width round-trips back through parseColumns unchanged", () => {
    const resized = applyColumnWidth(COLUMNS, "status", "320px");
    expect(parseColumns(serializeColumns(resized, FIELDS))).toEqual(resized);
  });
});
