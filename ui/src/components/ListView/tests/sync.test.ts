import { describe, expect, it } from "vitest";
// The Filter↔QuickFilter sync contract: both controls bind the SAME `Filter[]`
// (the SoT `useListView` owns), so a write through one surfaces through the
// other with no event plumbing. Verified here on the pure helpers — the wire
// output a Filter-bound host fetches with, and the quick-input value a
// QuickFilter renders — without mounting either component.
import { applyQuick, quickValue } from "../../QuickFilter/quickFilters";
import { serializeFilters } from "../../Filter/filters";
import type { Filter, FilterField } from "../../Filter/types";

const STATUS: FilterField = {
  label: "Status",
  value: "status",
  fieldname: "status",
  fieldtype: "Select",
  options: "Open\nClosed",
};
const CUSTOMER: FilterField = {
  label: "Customer",
  value: "customer",
  fieldname: "customer",
  fieldtype: "Link",
  options: "Customer",
};

describe("Filter ↔ QuickFilter sync over the shared list", () => {
  it("QuickFilter → Filter: a quick write lands in the wire filters", () => {
    const filters = applyQuick([], STATUS, "Open");
    expect(serializeFilters(filters)).toEqual([["status", "=", "Open"]]);
  });

  it("Filter → QuickFilter: a Filter-built condition shows in the quick input", () => {
    // A condition created in the Filter popover (its canonical operator).
    const filters: Filter[] = [
      { field: STATUS, fieldname: "status", operator: "equals", value: "Open" },
    ];
    expect(quickValue(filters, STATUS)).toBe("Open");
  });

  it("a Link like quick filter round-trips to a wrapped wire LIKE", () => {
    const filters = applyQuick([], CUSTOMER, "acme", "like");
    expect(quickValue(filters, CUSTOMER)).toBe("acme");
    expect(serializeFilters(filters)).toEqual([["customer", "LIKE", "%acme%"]]);
  });

  it("a quick filter coexists with a precise popover condition on the same field", () => {
    const precise: Filter[] = [
      {
        field: STATUS,
        fieldname: "status",
        operator: "in",
        value: ["Open", "Won"],
      },
    ];
    const both = applyQuick(precise, STATUS, "Closed");
    // The precise `in` survives untouched; the quick `equals` rides alongside.
    expect(serializeFilters(both)).toEqual([
      ["status", "in", ["Open", "Won"]],
      ["status", "=", "Closed"],
    ]);
    // The quick input reflects only its own condition.
    expect(quickValue(both, STATUS)).toBe("Closed");
  });
});
