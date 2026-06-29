import { describe, expect, it } from "vitest";
import {
  applyQuick,
  hasOperatorToggle,
  quickFilterOperator,
  quickFilterOperators,
  quickOperator,
  quickValue,
} from "../quickFilters";
import type { Filter, FilterField } from "../../Filter/types";

const STATUS: FilterField = {
  label: "Status",
  value: "status",
  fieldname: "status",
  fieldtype: "Select",
  options: "Open\nClosed",
};
const ACTIVE: FilterField = {
  label: "Active",
  value: "is_active",
  fieldname: "is_active",
  fieldtype: "Check",
};
const TITLE: FilterField = {
  label: "Title",
  value: "title",
  fieldname: "title",
  fieldtype: "Data",
};
const CUSTOMER: FilterField = {
  label: "Customer",
  value: "customer",
  fieldname: "customer",
  fieldtype: "Link",
  options: "Customer",
};

describe("quickFilterOperators / quickFilterOperator", () => {
  it("maps the equals-set fieldtypes to a single equals operator", () => {
    for (const ft of ["Check", "Select", "Autocomplete", "Date", "Datetime"]) {
      expect(quickFilterOperators(ft)).toEqual(["equals"]);
      expect(quickFilterOperator(ft)).toBe("equals");
    }
  });

  it("gives Link both like (default) and equals, surfaced as a toggle", () => {
    expect(quickFilterOperators("Link")).toEqual(["like", "equals"]);
    expect(quickFilterOperators("Dynamic Link")).toEqual(["like", "equals"]);
    expect(quickFilterOperator("Link")).toBe("like");
    expect(hasOperatorToggle("Link")).toBe(true);
  });

  it("defaults every other fieldtype to like-only (no toggle)", () => {
    for (const ft of ["Data", "Text", "Int", "Currency", "Duration"]) {
      expect(quickFilterOperators(ft)).toEqual(["like"]);
      expect(hasOperatorToggle(ft)).toBe(false);
    }
  });
});

describe("quickValue (read projection)", () => {
  it("surfaces the value of the field's canonical condition", () => {
    const filters: Filter[] = [
      { field: STATUS, fieldname: "status", operator: "equals", value: "Open" },
    ];
    expect(quickValue(filters, STATUS)).toBe("Open");
  });

  it("shows empty when the field carries only a non-owned condition", () => {
    // A popover-built `Status in [Open, Closed]` is not the Select canonical
    // (equals), so the quick input shows empty and leaves it untouched.
    const filters: Filter[] = [
      {
        field: STATUS,
        fieldname: "status",
        operator: "in",
        value: ["Open", "Closed"],
      },
    ];
    expect(quickValue(filters, STATUS)).toBe("");
  });

  it("maps a Check equals-Yes to a checked boolean, absent to unchecked", () => {
    const checked: Filter[] = [
      {
        field: ACTIVE,
        fieldname: "is_active",
        operator: "equals",
        value: "Yes",
      },
    ];
    expect(quickValue(checked, ACTIVE)).toBe(true);
    expect(quickValue([], ACTIVE)).toBe(false);
  });

  it("reads a Link via its like (default) or equals condition", () => {
    const likeCond: Filter[] = [
      {
        field: CUSTOMER,
        fieldname: "customer",
        operator: "like",
        value: "acme",
      },
    ];
    expect(quickValue(likeCond, CUSTOMER)).toBe("acme");
    expect(quickOperator(likeCond, CUSTOMER)).toBe("like");

    const equalsCond: Filter[] = [
      {
        field: CUSTOMER,
        fieldname: "customer",
        operator: "equals",
        value: "ACME Inc",
      },
    ];
    expect(quickValue(equalsCond, CUSTOMER)).toBe("ACME Inc");
    expect(quickOperator(equalsCond, CUSTOMER)).toBe("equals");
  });

  it("falls back to the field's default operator when none is set", () => {
    expect(quickOperator([], CUSTOMER)).toBe("like");
    expect(quickOperator([], STATUS)).toBe("equals");
  });
});

describe("applyQuick (write projection)", () => {
  it("appends a canonical condition when none exists", () => {
    expect(applyQuick([], STATUS, "Open")).toEqual([
      { field: STATUS, fieldname: "status", operator: "equals", value: "Open" },
    ]);
  });

  it("stores a like value bare (serializeFilters wraps the %)", () => {
    expect(applyQuick([], TITLE, "acme")).toEqual([
      { field: TITLE, fieldname: "title", operator: "like", value: "acme" },
    ]);
  });

  it("upserts in place rather than reordering", () => {
    const filters = applyQuick([], TITLE, "a");
    expect(applyQuick(filters, TITLE, "ac")).toEqual([
      { field: TITLE, fieldname: "title", operator: "like", value: "ac" },
    ]);
  });

  it("removes the condition when the value is cleared", () => {
    const filters = applyQuick([], TITLE, "acme");
    expect(applyQuick(filters, TITLE, "")).toEqual([]);
  });

  it("maps a Check checkbox to equals Yes / removed, never equals No", () => {
    const on = applyQuick([], ACTIVE, true);
    expect(on).toEqual([
      {
        field: ACTIVE,
        fieldname: "is_active",
        operator: "equals",
        value: "Yes",
      },
    ]);
    expect(applyQuick(on, ACTIVE, false)).toEqual([]);
  });

  it("appends a coexisting condition beside a non-owned one (never overwrites)", () => {
    const precise: Filter[] = [
      {
        field: STATUS,
        fieldname: "status",
        operator: "in",
        value: ["Open", "Won"],
      },
    ];
    expect(applyQuick(precise, STATUS, "Closed")).toEqual([
      ...precise,
      {
        field: STATUS,
        fieldname: "status",
        operator: "equals",
        value: "Closed",
      },
    ]);
  });

  it("leaves a non-owned condition intact when clearing an empty quick input", () => {
    const precise: Filter[] = [
      { field: STATUS, fieldname: "status", operator: "in", value: ["Open"] },
    ];
    expect(applyQuick(precise, STATUS, "")).toBe(precise);
  });

  it("toggles a Link between like and equals, replacing not duplicating", () => {
    const liked = applyQuick([], CUSTOMER, "acme", "like");
    expect(liked).toEqual([
      {
        field: CUSTOMER,
        fieldname: "customer",
        operator: "like",
        value: "acme",
      },
    ]);
    // Flip to equals: the like condition is replaced, not kept alongside.
    const equaled = applyQuick(liked, CUSTOMER, "ACME Inc", "equals");
    expect(equaled).toEqual([
      {
        field: CUSTOMER,
        fieldname: "customer",
        operator: "equals",
        value: "ACME Inc",
      },
    ]);
  });
});
