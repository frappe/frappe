import { describe, expect, it } from "vitest";
import { toLinkOption } from "../linkOption";

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
