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
const NAME: FilterField = {
  label: "Name",
  value: "name",
  fieldname: "name",
  fieldtype: "Link",
  options: "CRM Lead",
};

describe("quickFilterOperators / quickFilterOperator", () => {
  it("maps the equals-set fieldtypes to a single equals operator (no toggle)", () => {
    for (const ft of ["Check", "Select", "Autocomplete", "Date", "Datetime"]) {
      const field = { ...TITLE, fieldtype: ft };
      expect(quickFilterOperators(field)).toEqual(["equals"]);
      expect(quickFilterOperator(field)).toBe("equals");
      expect(hasOperatorToggle(field)).toBe(false);
    }
  });

  it("gives Link / Dynamic Link a single equals (Link pick, no toggle)", () => {
    expect(quickFilterOperators(CUSTOMER)).toEqual(["equals"]);
    expect(quickFilterOperator(CUSTOMER)).toBe("equals");
    expect(hasOperatorToggle(CUSTOMER)).toBe(false);
    const dyn = { ...CUSTOMER, fieldtype: "Dynamic Link" };
    expect(quickFilterOperators(dyn)).toEqual(["equals"]);
    expect(hasOperatorToggle(dyn)).toBe(false);
  });

  it("gives text fields like (default) + equals, surfaced as a toggle", () => {
    for (const ft of [
      "Data",
      "Small Text",
      "Text",
      "Long Text",
      "Text Editor",
    ]) {
      const field = { ...TITLE, fieldtype: ft };
      expect(quickFilterOperators(field)).toEqual(["like", "equals"]);
      expect(quickFilterOperator(field)).toBe("like");
      expect(hasOperatorToggle(field)).toBe(true);
    }
  });

  it("keeps Number/Duration fields like-only (no toggle, no prefix slot to host one)", () => {
    for (const ft of ["Int", "Float", "Currency", "Percent", "Duration"]) {
      const field = { ...TITLE, fieldtype: ft };
      expect(quickFilterOperators(field)).toEqual(["like"]);
      expect(hasOperatorToggle(field)).toBe(false);
    }
  });

  it("treats the name field as free-text (toggle), despite its Link fieldtype", () => {
    expect(quickFilterOperators(NAME)).toEqual(["like", "equals"]);
    expect(quickFilterOperator(NAME)).toBe("like");
    expect(hasOperatorToggle(NAME)).toBe(true);
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

  it("reads a free-text field via its like (default) or equals condition", () => {
    const likeCond: Filter[] = [
      { field: TITLE, fieldname: "title", operator: "like", value: "acme" },
    ];
    expect(quickValue(likeCond, TITLE)).toBe("acme");
    expect(quickOperator(likeCond, TITLE)).toBe("like");

    const equalsCond: Filter[] = [
      { field: TITLE, fieldname: "title", operator: "equals", value: "ACME" },
    ];
    expect(quickValue(equalsCond, TITLE)).toBe("ACME");
    expect(quickOperator(equalsCond, TITLE)).toBe("equals");
  });

  it("reads a Link via its single equals condition", () => {
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
    expect(quickOperator([], CUSTOMER)).toBe("equals");
    expect(quickOperator([], STATUS)).toBe("equals");
    expect(quickOperator([], TITLE)).toBe("like");
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

  it("toggles a free-text field between like and equals, replacing not duplicating", () => {
    const liked = applyQuick([], TITLE, "acme", "like");
    expect(liked).toEqual([
      { field: TITLE, fieldname: "title", operator: "like", value: "acme" },
    ]);
    // Flip to equals: the like condition is replaced, not kept alongside.
    const equaled = applyQuick(liked, TITLE, "acme", "equals");
    expect(equaled).toEqual([
      { field: TITLE, fieldname: "title", operator: "equals", value: "acme" },
    ]);
  });

  it("edits only the first owned condition, preserving a sibling duplicate", () => {
    // The Filter popover allows two `status equals …` conditions; the quick input
    // projects the first, so editing it must leave the second intact.
    const dupes: Filter[] = [
      { field: STATUS, fieldname: "status", operator: "equals", value: "Open" },
      { field: STATUS, fieldname: "status", operator: "equals", value: "Won" },
    ];
    expect(applyQuick(dupes, STATUS, "Closed")).toEqual([
      {
        field: STATUS,
        fieldname: "status",
        operator: "equals",
        value: "Closed",
      },
      { field: STATUS, fieldname: "status", operator: "equals", value: "Won" },
    ]);
  });

  it("clears every owned condition for the field", () => {
    // Quick Filter is authoritative: clearing removes *all* owned conditions,
    // including a sibling duplicate the popover allows.
    const dupes: Filter[] = [
      { field: STATUS, fieldname: "status", operator: "equals", value: "Open" },
      { field: STATUS, fieldname: "status", operator: "equals", value: "Won" },
    ];
    expect(applyQuick(dupes, STATUS, "")).toEqual([]);
  });

  it("coerces an unowned operator on a Link to its single equals", () => {
    // A Link owns only `equals`; a stray `like` request falls back to it.
    expect(applyQuick([], CUSTOMER, "ACME Inc", "like")).toEqual([
      {
        field: CUSTOMER,
        fieldname: "customer",
        operator: "equals",
        value: "ACME Inc",
      },
    ]);
  });
});
