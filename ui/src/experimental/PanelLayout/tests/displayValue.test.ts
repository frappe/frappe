import { describe, expect, it } from "vitest";
import {
  displayValue,
  isEmptyValue,
  isSummaryField,
  summarize,
} from "../displayValue";
import type { FieldMeta } from "../../../components/Fields/types";

function field(fieldtype: string, extra: Partial<FieldMeta> = {}): FieldMeta {
  return { fieldname: "f", fieldtype, label: "F", ...extra };
}

describe("isSummaryField", () => {
  it("covers the fieldtypes with no honest row", () => {
    for (const t of [
      "Table",
      "Text Editor",
      "Code",
      "Geolocation",
      "Image",
      "Attach",
    ])
      expect(isSummaryField(t)).toBe(true);
  });

  it("leaves the rest to a control", () => {
    for (const t of ["Data", "Link", "Select", "Check", "Currency", "Date"])
      expect(isSummaryField(t)).toBe(false);
  });
});

describe("isEmptyValue", () => {
  it("reads null, blank and an empty table as unset", () => {
    expect(isEmptyValue(null)).toBe(true);
    expect(isEmptyValue(undefined)).toBe(true);
    expect(isEmptyValue("")).toBe(true);
    expect(isEmptyValue([])).toBe(true);
  });

  it("keeps zero and false as values", () => {
    expect(isEmptyValue(0)).toBe(false);
    expect(isEmptyValue(false)).toBe(false);
  });
});

describe("summarize", () => {
  it("counts child rows, singular and plural", () => {
    expect(summarize([{}, {}, {}], "Table")).toBe("3 items");
    expect(summarize([{}], "Table")).toBe("1 item");
  });

  it("takes the first non-empty line of rich text, without its markup", () => {
    expect(summarize("<p></p><p>Hello <b>there</b></p>", "Text Editor")).toBe(
      "Hello there",
    );
  });

  it("takes the first line of code verbatim", () => {
    expect(summarize("const a = 1\nconst b = 2", "Code")).toBe("const a = 1");
  });

  it("falls back to Set and Not set", () => {
    expect(summarize("/files/a.png", "Image")).toBe("Set");
    expect(summarize("", "Attach")).toBe("Not set");
    expect(summarize([], "Table")).toBe("Not set");
  });
});

describe("displayValue", () => {
  it("returns an empty string for an unset value, so the row shows its placeholder", () => {
    expect(displayValue(null, field("Data"))).toBe("");
    expect(displayValue("", field("Link"))).toBe("");
  });

  it("gives a Check no unset state", () => {
    expect(displayValue(1, field("Check"))).toBe("Yes");
    expect(displayValue(0, field("Check"))).toBe("No");
    expect(displayValue(undefined, field("Check"))).toBe("No");
  });

  it("formats numeric fieldtypes through formatField", () => {
    expect(displayValue(1234567, field("Int"))).toBe("1234567");
    expect(displayValue(1234.5, field("Float"), { precision: 2 })).toBe(
      "1,234.50",
    );
    expect(
      displayValue(1234.5, field("Currency"), {
        precision: 2,
        currency: "USD",
      }),
    ).toBe("$ 1,234.50");
  });

  it("renders a link as its raw name", () => {
    expect(displayValue("CRM-LEAD-0001", field("Link"))).toBe("CRM-LEAD-0001");
  });

  it("summarizes the fieldtypes with no honest row", () => {
    expect(displayValue([{}, {}], field("Table"))).toBe("2 items");
  });
});
