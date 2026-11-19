import { describe, expect, it } from "vitest";
import { newRowValues } from "../../FormLayout/newRowValues";
import { displayValue } from "../../FormLayout/displayValue";
import { fieldChoices } from "../choices";
import type { FieldMeta } from "../types";

const select = (extra: Partial<FieldMeta>): FieldMeta => ({ fieldname: "f", fieldtype: "Select", ...extra });

describe("fieldChoices", () => {
  it("splits the options, each its own label", () => {
    expect(fieldChoices(select({ options: "\nOpen\nWon" }))).toEqual([
      { value: "", label: "" },
      { value: "Open", label: "Open" },
      { value: "Won", label: "Won" },
    ]);
  });

  it("tidies the lines of an Autocomplete", () => {
    expect(fieldChoices(select({ options: " Open \n\nWon" }), true).map((one) => one.value)).toEqual([
      "Open",
      "Won",
    ]);
  });

  it("prefers the pairs a script set", () => {
    const choices = [{ value: "first_name", label: "First Name" }];
    expect(fieldChoices(select({ options: "first_name", choices }))).toBe(choices);
  });

  it("tidies the pairs of an Autocomplete the same way", () => {
    const choices = [{ value: " ", label: "blank" }, { value: "a", label: "A" }];
    expect(fieldChoices(select({ choices }), true)).toEqual([{ value: "a", label: "A" }]);
    expect(fieldChoices(select({ choices }))).toBe(choices);
  });

  it("is empty without options", () => {
    expect(fieldChoices(select({}), true)).toEqual([]);
  });
});

describe("displayValue of a labelled choice", () => {
  const choices = [{ value: "first_name", label: "First Name" }];

  it("shows the label of a Select and an Autocomplete", () => {
    expect(displayValue("first_name", select({ choices }))).toBe("First Name");
    expect(displayValue("first_name", select({ fieldtype: "Autocomplete", choices }))).toBe("First Name");
  });

  it("matches a number to its choice", () => {
    expect(displayValue(1, select({ choices: [{ value: "1", label: "One" }] }))).toBe("One");
  });

  it("shows a value no choice names as it is", () => {
    expect(displayValue("other", select({ choices }))).toBe("other");
    expect(displayValue("Open", select({ options: "Open" }))).toBe("Open");
  });
});

describe("a new row's default", () => {
  it("is the first choice's value, not its label", () => {
    const choices = [{ value: "first_name", label: "First Name" }];
    expect(newRowValues([select({ fieldname: "mapped_to", choices, options: "first_name" })])).toMatchObject({
      mapped_to: "first_name",
    });
  });
});
