import { describe, expect, it } from "vitest";
// useFilters owns the shared FilterCondition[] both the Filter and QuickFilter
// controls bind, plus the wire projection a host fetches with. No Meta — the
// conditions carry their own field — so this exercises the composable directly.
import { useFilters } from "../useFilters";
import type { FilterField } from "../types";

const STATUS: FilterField = {
  label: "Status",
  value: "status",
  fieldname: "status",
  fieldtype: "Select",
  options: "Open\nClosed",
};

describe("useFilters", () => {
  it("starts with no conditions and an empty wire list", () => {
    const { conditions, wire } = useFilters();
    expect(conditions.value).toEqual([]);
    expect(wire.value).toEqual([]);
  });

  it("projects the conditions to the Frappe wire filter list", () => {
    const { conditions, wire } = useFilters();
    conditions.value = [
      { field: STATUS, fieldname: "status", operator: "equals", value: "Open" },
    ];
    expect(wire.value).toEqual([["status", "=", "Open"]]);
  });

  it("keeps the wire output in sync as conditions change", () => {
    const { conditions, wire } = useFilters();
    conditions.value = [
      { field: STATUS, fieldname: "status", operator: "equals", value: "Open" },
    ];
    expect(wire.value).toEqual([["status", "=", "Open"]]);
    conditions.value = [];
    expect(wire.value).toEqual([]);
  });
});
