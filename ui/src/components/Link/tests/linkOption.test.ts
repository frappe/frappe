import { describe, expect, it } from "vitest";
import { toIdOption, toLinkOption } from "../linkOption";

describe("toLinkOption", () => {
  it("leaves the record's name out of a titled option's description", () => {
    expect(
      toLinkOption({ value: "62e34b24e4", label: "tabPartner", description: "62e34b24e4, frappe.io" })
    ).toEqual({ value: "62e34b24e4", label: "tabPartner", description: "frappe.io" });
  });

  it("drops a description that held only the name, and labels an untitled option by its name", () => {
    expect(toLinkOption({ value: "2i3h26h74o", description: "2i3h26h74o" })).toEqual({
      value: "2i3h26h74o",
      label: "2i3h26h74o",
      description: undefined,
    });
  });
});

describe("toIdOption", () => {
  it("labels a titled record by its ID and moves the title into the description", () => {
    expect(
      toIdOption({ value: "9500", label: "Rebate calculation", description: "9500, Open, jo@example.com" })
    ).toEqual({ value: "9500", label: "9500", description: "Rebate calculation, Open, jo@example.com" });
  });

  it("labels an untitled record by its ID with no description", () => {
    expect(toIdOption({ value: "9500", description: "9500" })).toEqual({
      value: "9500",
      label: "9500",
      description: undefined,
    });
  });
});
