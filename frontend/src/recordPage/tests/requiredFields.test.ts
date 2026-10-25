// The mandatory check a save and a dialog share: what it marks, what it skips, and the refusal it names.
import { describe, expect, it } from "vitest";
import { fieldsToLayout } from "@framework/ui/components/FormLayout/fieldsToLayout";
import type { FieldNode, FormLayoutSchema } from "@framework/ui/components/FormLayout/types";
import { missingRequired, requiredRefusal, shownFields } from "../requiredFields";

const summary: FieldNode = { fieldname: "summary", fieldtype: "Small Text", label: "Summary", reqd: true };
const reason: FieldNode = {
  fieldname: "reason",
  fieldtype: "Small Text",
  label: "Reason",
  reqd: true,
  dependsOn: "eval:doc.summary == 'lost'",
};
const items: FieldNode = {
  fieldname: "items",
  fieldtype: "Table",
  label: "Items",
  options: "Deal Item",
  childLayout: fieldsToLayout([
    { fieldname: "item", fieldtype: "Data", label: "Item", reqd: true },
    { fieldname: "note", fieldtype: "Data", label: "Note", reqd: true, dependsOn: "eval:doc.item == 'x'" },
  ]),
};

describe("missingRequired", () => {
  const layout = fieldsToLayout([summary, reason]);

  it("marks each empty mandatory field with its label", () => {
    expect(missingRequired(layout, {})).toEqual([
      { address: "summary", message: "Summary is required", shownIn: "Summary" },
    ]);
  });

  it("does not demand a field its depends_on has hidden", () => {
    expect(missingRequired(layout, { summary: "won" })).toEqual([]);
  });

  it("demands a conditional field once it is on screen", () => {
    expect(missingRequired(layout, { summary: "lost" }).map((one) => one.address)).toEqual([
      "reason",
    ]);
  });

  it("checks a child row's cells against the row, addressed by the row's key", () => {
    const doc = { items: [{ name: "row-a", item: "" }, { name: "row-b", item: "x" }] };

    expect(missingRequired(fieldsToLayout([items]), doc)).toEqual([
      {
        address: { parentfield: "items", key: "name:row-a", fieldname: "item" },
        message: "Item is required",
        shownIn: "Items",
      },
      {
        address: { parentfield: "items", key: "name:row-b", fieldname: "note" },
        message: "Note is required",
        shownIn: "Items",
      },
    ]);
  });

  it("skips a cell its row dialog hides in a section", () => {
    const table: FieldNode = {
      ...items,
      childLayout: [
        {
          sections: [
            { columns: [{ fields: [{ fieldname: "item", fieldtype: "Data", label: "Item", reqd: true }] }] },
            {
              dependsOn: "eval:doc.item == 'x'",
              columns: [{ fields: [{ fieldname: "note", fieldtype: "Data", label: "Note", reqd: true }] }],
            },
          ],
        },
      ],
    };

    expect(missingRequired(fieldsToLayout([table]), { items: [{ name: "a", item: "y" }] })).toEqual([]);
  });

  it("demands a mandatory table with no rows", () => {
    const layout = fieldsToLayout([{ ...items, reqd: true }]);

    expect(missingRequired(layout, { items: [] }).map((one) => one.address)).toEqual(["items"]);
  });

  it("skips a field on a tab or section that does not show", () => {
    const layout: FormLayoutSchema = [
      { label: "Main", sections: [{ columns: [{ fields: [summary] }], hidden: true }] },
      { label: "More", override: { hidden: true }, sections: [{ columns: [{ fields: [reason] }] }] },
    ];

    expect(missingRequired(layout, { summary: "lost" })).toEqual([]);
  });
});

describe("shownFields", () => {
  it("lists the top-level fields on screen, in form order", () => {
    const layout = fieldsToLayout([summary, reason, items]);

    expect(shownFields(layout, { summary: "won" }).map((field) => field.fieldname)).toEqual([
      "summary",
      "items",
    ]);
  });
});

describe("requiredRefusal", () => {
  it("names each field once, a row cell by its table", () => {
    const missing = missingRequired(fieldsToLayout([summary, items]), {
      items: [{ name: "a" }, { name: "b" }],
    });

    expect(requiredRefusal(missing)).toBe("Please fill in Summary, Items");
  });
});
