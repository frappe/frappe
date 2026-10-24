import { describe, expect, it } from "vitest";
import {
  displayValue,
  isEmptyValue,
  isSummaryField,
  summarize,
} from "../displayValue";
import type { FieldMeta } from "@framework/ui/components/Fields/types";

function field(fieldtype: string, extra: Partial<FieldMeta> = {}): FieldMeta {
  return { fieldname: "f", fieldtype, label: "F", ...extra };
}

describe("isSummaryField", () => {
  it("covers the fieldtypes with no honest row", () => {
    for (const t of [
      "Table",
      "Text Editor",
      "Code",
      "JSON",
      "Markdown Editor",
      "HTML Editor",
      "Geolocation",
      "Image",
      "Attach",
      "Attach Image",
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

  it("takes the first line of the other code-family editors", () => {
    expect(summarize('{\n  "a": 1\n}', "JSON")).toBe("{");
    expect(summarize("# Title\nbody", "Markdown Editor")).toBe("# Title");
    expect(summarize("<div>\n</div>", "HTML Editor")).toBe("<div>");
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

  const linkTitles = {
    "Customer::CUST-0001": "Acme Corp",
    "Customer::CUST-0002": "TechStart Inc",
  };

  it("shows a link's title, and its name when it has none", () => {
    const link = field("Link", { options: "Customer" });
    expect(displayValue("CUST-0001", link, { linkTitles })).toBe("Acme Corp");
    expect(displayValue("CUST-0009", link, { linkTitles })).toBe("CUST-0009");
  });

  it("shows a dynamic link's title, from the doctype its sibling names", () => {
    const dynamic = field("Dynamic Link", { options: "link_doctype" });
    const doc = { link_doctype: "Customer" };
    expect(displayValue("CUST-0002", dynamic, { doc, linkTitles })).toBe(
      "TechStart Inc",
    );
  });

  it("joins a Table MultiSelect's linked titles", () => {
    const multi = field("Table MultiSelect", {
      childFields: [
        { fieldname: "customer", fieldtype: "Link", options: "Customer" },
      ],
    });
    const rows = [{ customer: "CUST-0001" }, { customer: "CUST-0002" }];
    expect(displayValue(rows, multi, { linkTitles })).toBe(
      "Acme Corp, TechStart Inc",
    );
    expect(displayValue([], multi)).toBe("");
  });

  it("summarizes an Image from the field its options name", () => {
    const image = field("Image", { options: "photo" });
    expect(displayValue(null, image, { doc: { photo: "/files/a.png" } })).toBe(
      "Set",
    );
    expect(displayValue(null, image, { doc: {} })).toBe("Not set");
  });

  it("summarizes an Attach Image as Attach does", () => {
    expect(displayValue("/files/a.png", field("Attach Image"))).toBe("Set");
  });

  it("shows a rating as stars out of the star count", () => {
    expect(displayValue(0.6, field("Rating"))).toBe("3 / 5");
    expect(displayValue(0.5, field("Rating", { options: "10" }))).toBe(
      "5 / 10",
    );
  });

  it("formats a duration as the form's control does", () => {
    expect(displayValue(5445, field("Duration"))).toBe("1h 30m 45s");
  });

  it("shows a time as the form's picker does", () => {
    expect(displayValue("9:15:00", field("Time"))).toBe("09:15");
    expect(displayValue("14:05:30.000000", field("Time"))).toBe("14:05");
  });

  it("masks a password, typed or saved", () => {
    expect(displayValue("hunter2", field("Password"))).toBe("••••••••");
    expect(displayValue("*******", field("Password"))).toBe("••••••••");
  });

  it("summarizes the fieldtypes with no honest row", () => {
    expect(displayValue([{}, {}], field("Table"))).toBe("2 items");
  });
});
