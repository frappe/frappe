import { describe, expect, it } from "vitest";
import { dependsOnScope, fromDependsOn, toDependsOn } from "../dependsOn";
import { evaluateDependsOn } from "../../FormLayout/dependsOn";
import type { ConditionGroup, FieldConditionValue } from "../types";

type Tree = ConditionGroup<FieldConditionValue>;

function leaf(
  fieldname: string,
  operator: FieldConditionValue["operator"],
  value: FieldConditionValue["value"]
): FieldConditionValue {
  return { fieldname, operator, value };
}

function group(
  conditions: Tree["conditions"],
  conjunction: Tree["conjunction"] = "and"
): Tree {
  return { conjunction, conditions };
}

/** An invoice row's view: its own fields, its invoice's as `parent.`, submittable. */
const scope = dependsOnScope(
  [
    { fieldname: "is_pos", fieldtype: "Check", label: "Is POS" },
    {
      fieldname: "customer",
      fieldtype: "Link",
      label: "Customer",
      options: "Customer",
    },
    {
      fieldname: "status",
      fieldtype: "Select",
      label: "Status",
      options: "Draft\nPaid\nUnpaid",
    },
    { fieldname: "grand_total", fieldtype: "Currency", label: "Grand Total" },
    { fieldname: "posting_date", fieldtype: "Date", label: "Posting Date" },
    { fieldname: "remarks", fieldtype: "Small Text", label: "Remarks" },
    { fieldname: "uom", fieldtype: "Link", label: "UOM", options: "UOM" },
    {
      fieldname: "stock_uom",
      fieldtype: "Link",
      label: "Stock UOM",
      options: "UOM",
    },
    {
      fieldname: "items",
      fieldtype: "Table",
      label: "Items",
      options: "Sales Invoice Item",
    },
    { fieldname: "phone", fieldtype: "Phone", label: "Phone" },
    { fieldname: "details", fieldtype: "Section Break", label: "Details" },
  ],
  {
    parentFields: [
      { fieldname: "is_return", fieldtype: "Check", label: "Is Return" },
    ],
    submittable: true,
  }
);

describe("dependsOnScope", () => {
  it("offers each field with a value, the parent's, and the record's own", () => {
    expect(scope.fields.map((field) => [field.label, field.fieldtype])).toEqual(
      [
        ["Is POS", "Check"],
        ["Customer", "Link"],
        ["Status", "Select"],
        ["Grand Total", "Currency"],
        ["Posting Date", "Date"],
        ["Remarks", "Small Text"],
        ["UOM", "Link"],
        ["Stock UOM", "Link"],
        ["Items (has rows)", "Check"],
        ["Phone", "Data"],
        ["Parent: Is Return", "Check"],
        ["Record is new", "Check"],
        ["Document status", "Select"],
      ]
    );
  });

  it("leaves Document status out of a DocType that is not submittable", () => {
    const plain = dependsOnScope([{ fieldname: "title", fieldtype: "Data" }]);
    expect(plain.fields.map((field) => field.fieldname)).toEqual([
      "title",
      "__islocal",
    ]);
  });
});

describe("fromDependsOn and toDependsOn", () => {
  it("read nothing as an empty tree and write an empty tree as nothing", () => {
    expect(fromDependsOn("", scope)).toEqual(group([]));
    expect(fromDependsOn(undefined, scope)).toEqual(group([]));
    expect(fromDependsOn("eval:", scope)).toEqual(group([]));
    expect(toDependsOn(group([]), scope)).toBe("");
    expect(toDependsOn(null, scope)).toBe("");
  });

  // Each row: the tree, the string it is written as, and back.
  it.each<[string, Tree, string]>([
    ["a Check that is on", group([leaf("is_pos", "equals", "Yes")]), "is_pos"],
    [
      "a Check that is off",
      group([leaf("is_pos", "equals", "No")]),
      "eval:!doc.is_pos",
    ],
    ["a field that is set", group([leaf("customer", "is", "set")]), "customer"],
    [
      "a field that is empty",
      group([leaf("customer", "is", "not set")]),
      "eval:!doc.customer",
    ],
    [
      "a text value",
      group([leaf("status", "equals", "Paid")]),
      'eval:doc.status === "Paid"',
    ],
    [
      "an unequal value",
      group([leaf("status", "not equals", "Paid")]),
      'eval:doc.status !== "Paid"',
    ],
    [
      "a number",
      group([leaf("grand_total", ">", 1000)]),
      "eval:doc.grand_total > 1000",
    ],
    [
      "a date",
      group([leaf("posting_date", "<=", "2026-01-31")]),
      'eval:doc.posting_date <= "2026-01-31"',
    ],
    [
      "a quote in a value",
      group([leaf("remarks", "equals", 'say "hi"\n')]),
      'eval:doc.remarks === "say \\"hi\\"\\n"',
    ],
    [
      "a record that is new",
      group([leaf("__islocal", "equals", "Yes")]),
      "eval:doc.__islocal",
    ],
    [
      "a record that is saved",
      group([leaf("__islocal", "equals", "No")]),
      "eval:!doc.__islocal",
    ],
    [
      "a document status",
      group([leaf("docstatus", "equals", "Submitted")]),
      "eval:doc.docstatus === 1",
    ],
    [
      "a document status left",
      group([leaf("docstatus", "not equals", "Draft")]),
      "eval:doc.docstatus !== 0",
    ],
    [
      "statuses",
      group([leaf("docstatus", "in", ["Draft", "Cancelled"])]),
      "eval:[0, 2].includes(doc.docstatus)",
    ],
    ["a table with rows", group([leaf("items", "equals", "Yes")]), "items"],
    [
      "a table with no rows",
      group([leaf("items", "equals", "No")]),
      "eval:!doc.items.length",
    ],
    [
      "a parent's Check",
      group([leaf("parent.is_return", "equals", "Yes")]),
      "eval:parent.is_return",
    ],
    [
      "a parent's Check off",
      group([leaf("parent.is_return", "equals", "No")]),
      "eval:!parent.is_return",
    ],
    [
      "another field",
      group([leaf("uom", "not equals", "eval:doc.stock_uom")]),
      "eval:doc.uom !== doc.stock_uom",
    ],
    [
      "a parent field",
      group([leaf("is_pos", "equals", "eval:parent.is_return")]),
      "eval:doc.is_pos === parent.is_return",
    ],
    [
      "picked values",
      group([leaf("status", "in", ["Paid", "Unpaid"])]),
      'eval:["Paid", "Unpaid"].includes(doc.status)',
    ],
    [
      "values left out",
      group([leaf("customer", "not in", ["A", "B"])]),
      'eval:!["A", "B"].includes(doc.customer)',
    ],
    [
      "typed values",
      group([leaf("remarks", "in", "a, b")]),
      'eval:["a", "b"].includes(doc.remarks)',
    ],
    [
      "typed numbers",
      group([leaf("grand_total", "not in", "10, 20")]),
      "eval:![10, 20].includes(doc.grand_total)",
    ],
    [
      "text inside",
      group([leaf("remarks", "like", "urgent")]),
      'eval:(doc.remarks || "").includes("urgent")',
    ],
    [
      "text not inside",
      group([leaf("customer", "not like", "Corp")]),
      'eval:!(doc.customer || "").includes("Corp")',
    ],
    [
      "digits inside",
      group([leaf("grand_total", "like", "99")]),
      'eval:String(doc.grand_total ?? "").includes("99")',
    ],
    [
      "a date range",
      group([leaf("posting_date", "between", ["2026-01-01", "2026-01-31"])]),
      'eval:("2026-01-01" <= doc.posting_date && doc.posting_date <= "2026-01-31")',
    ],
    [
      "rows that all hold",
      group([leaf("is_pos", "equals", "Yes"), leaf("customer", "is", "set")]),
      "eval:doc.is_pos && doc.customer",
    ],
    [
      "rows of which one holds",
      group(
        [leaf("is_pos", "equals", "Yes"), leaf("customer", "is", "set")],
        "or"
      ),
      "eval:doc.is_pos || doc.customer",
    ],
    [
      "a group in a group",
      group([
        leaf("is_pos", "equals", "Yes"),
        group(
          [leaf("status", "equals", "Paid"), leaf("grand_total", ">", 0)],
          "or"
        ),
      ]),
      'eval:doc.is_pos && (doc.status === "Paid" || doc.grand_total > 0)',
    ],
    [
      "a group like its parent",
      group([
        leaf("is_pos", "equals", "Yes"),
        group([leaf("customer", "is", "set"), leaf("remarks", "is", "set")]),
      ]),
      "eval:doc.is_pos && (doc.customer && doc.remarks)",
    ],
    [
      "a range among rows",
      group(
        [
          leaf("posting_date", "between", ["2026-01-01", "2026-12-31"]),
          leaf("is_pos", "equals", "No"),
        ],
        "or"
      ),
      'eval:("2026-01-01" <= doc.posting_date && doc.posting_date <= "2026-12-31") || !doc.is_pos',
    ],
  ])("round-trip %s", (_, tree, text) => {
    expect(toDependsOn(tree, scope)).toBe(text);
    expect(fromDependsOn(text, scope)).toEqual(tree);
  });
});

/** Conditions as people write them, and the tree each reads as. */
const WRITTEN: [string, string, Tree][] = [
  [
    "loose equality",
    'eval:doc.status=="Paid"',
    group([leaf("status", "equals", "Paid")]),
  ],
  [
    "single quotes and a semicolon",
    "eval: doc.status != 'Paid';",
    group([leaf("status", "not equals", "Paid")]),
  ],
  [
    "a Check against 1",
    "eval:doc.is_pos == 1",
    group([leaf("is_pos", "equals", "Yes")]),
  ],
  [
    "a Check against 0",
    "eval:doc.is_pos === 0",
    group([leaf("is_pos", "equals", "No")]),
  ],
  [
    "a Check against text",
    'eval:doc.is_pos != "1"',
    group([leaf("is_pos", "equals", "No")]),
  ],
  [
    "a number written as text",
    'eval:doc.grand_total >= "100"',
    group([leaf("grand_total", ">=", 100)]),
  ],
  [
    "the value first",
    "eval:100 < doc.grand_total",
    group([leaf("grand_total", ">", 100)]),
  ],
  [
    "a negative number",
    "eval:doc.grand_total > -5",
    group([leaf("grand_total", ">", -5)]),
  ],
  [
    "no value",
    'eval:doc.remarks === ""',
    group([leaf("remarks", "equals", "")]),
  ],
  [
    "in_list",
    'eval:in_list(["Paid", "Unpaid"], doc.status)',
    group([leaf("status", "in", ["Paid", "Unpaid"])]),
  ],
  [
    "indexOf found",
    'eval:["A"].indexOf(doc.customer) !== -1',
    group([leaf("customer", "in", ["A"])]),
  ],
  [
    "indexOf missing",
    'eval:["A"].indexOf(doc.customer) == -1',
    group([leaf("customer", "not in", ["A"])]),
  ],
  [
    "includes on the field",
    'eval:doc.remarks.includes("x")',
    group([leaf("remarks", "like", "x")]),
  ],
  [
    "a negated includes",
    'eval:!doc.remarks.includes("x")',
    group([leaf("remarks", "not like", "x")]),
  ],
  [
    "rows counted",
    "eval:doc.items.length > 0",
    group([leaf("items", "equals", "Yes")]),
  ],
  [
    "no rows counted",
    "eval:doc.items.length === 0",
    group([leaf("items", "equals", "No")]),
  ],
  [
    "a parenthesised negation",
    'eval:!(doc.status === "Paid")',
    group([leaf("status", "not equals", "Paid")]),
  ],
  [
    "a double negation",
    "eval:!!doc.customer",
    group([leaf("customer", "is", "set")]),
  ],
  [
    "a numeric status",
    "eval:doc.docstatus==0",
    group([leaf("docstatus", "equals", "Draft")]),
  ],
  ["a Phone read as text", "phone", group([leaf("phone", "is", "set")])],
  [
    "&& before ||",
    "eval:doc.is_pos || doc.customer && doc.remarks",
    group(
      [
        leaf("is_pos", "equals", "Yes"),
        group([leaf("customer", "is", "set"), leaf("remarks", "is", "set")]),
      ],
      "or"
    ),
  ],
  [
    "parentheses around the whole",
    "eval:(doc.is_pos || doc.customer)",
    group(
      [leaf("is_pos", "equals", "Yes"), leaf("customer", "is", "set")],
      "or"
    ),
  ],
];

describe("fromDependsOn", () => {
  it.each(WRITTEN)("reads %s", (_, text, tree) => {
    expect(fromDependsOn(text, scope)).toEqual(tree);
  });

  it.each(WRITTEN)("writes %s back as the tree it read", (_, text) => {
    const tree = fromDependsOn(text, scope)!;
    expect(fromDependsOn(toDependsOn(tree, scope), scope)).toEqual(tree);
  });

  // Each of these would read as a row that means something else, or as none.
  it.each([
    ["an unknown field", "eval:doc.nope"],
    ["a bare unknown field", "nope"],
    ["a table without length", "eval:doc.items"],
    ["a field's own property", "eval:doc.customer.name"],
    ["a call", "eval:cint(doc.grand_total) > 0"],
    ["frappe", 'eval:frappe.user.has_role("System Manager")'],
    ["a negated group", "eval:!(doc.is_pos && doc.customer)"],
    ["a negated comparison", 'eval:!doc.status === "Paid"'],
    ["a negated ordering", "eval:!(doc.grand_total > 0)"],
    ["a comparison with null", "eval:doc.customer != null"],
    ["a Check against 2", "eval:doc.is_pos == 2"],
    ["a status order", "eval:doc.docstatus < 2"],
    ["a status of 3", "eval:doc.docstatus === 3"],
    ["an assignment", "eval:doc.status = 'Paid'"],
    ["a ternary", "eval:doc.is_pos ? 1 : 0"],
    ["a template", "eval:`${doc.status}`"],
    ["an empty list", "eval:[].includes(doc.status)"],
    ["a parent with no parent", "eval:parent.company"],
    ["an indexOf bound", 'eval:["A"].indexOf(doc.customer) > 0'],
    ["two values", 'eval:"a" === "b"'],
    ["an unterminated string", 'eval:doc.status === "Paid'],
    ["code after", "eval:doc.is_pos doc.customer"],
    ["a dotted bare name", "doc.is_pos"],
  ])("keeps %s as code", (_, text) => {
    expect(fromDependsOn(text, scope)).toBeNull();
  });
});

describe("toDependsOn", () => {
  it("drops unfinished rows and the groups they leave", () => {
    const tree = group([
      leaf("", "equals", ""),
      leaf("posting_date", "equals", null),
      leaf("status", "in", []),
      leaf("remarks", "like", ""),
      leaf("posting_date", "between", ["2026-01-01", null]),
      group([leaf("customer", "is", "set")], "or"),
      group([]),
    ]);
    expect(toDependsOn(tree, scope)).toBe("customer");
  });

  it("writes Is not set as empty", () => {
    expect(toDependsOn(group([leaf("customer", "is not", "set")]), scope)).toBe(
      "eval:!doc.customer"
    );
  });

  // The oracle is desk v2's own evaluator, so the written code is checked by what it does.
  it.each<[string, Tree, Record<string, unknown>, boolean]>([
    [
      "text inside an empty field",
      group([leaf("remarks", "like", "x")]),
      { remarks: null },
      false,
    ],
    [
      "digits inside a number",
      group([leaf("grand_total", "like", "99")]),
      { grand_total: 1990 },
      true,
    ],
    [
      "a table with rows",
      group([leaf("items", "equals", "Yes")]),
      { items: [{}] },
      true,
    ],
    [
      "a table with none",
      group([leaf("items", "equals", "Yes")]),
      { items: [] },
      false,
    ],
    [
      "a status",
      group([leaf("docstatus", "in", ["Submitted"])]),
      { docstatus: 1 },
      true,
    ],
    [
      "a date in range",
      group([leaf("posting_date", "between", ["2026-01-01", "2026-01-31"])]),
      { posting_date: "2026-01-15" },
      true,
    ],
    [
      "a date out of range",
      group([leaf("posting_date", "between", ["2026-01-01", "2026-01-31"])]),
      { posting_date: "2026-02-01" },
      false,
    ],
    [
      "two fields",
      group([leaf("uom", "equals", "eval:doc.stock_uom")]),
      { uom: "Nos", stock_uom: "Nos" },
      true,
    ],
  ])("writes code that does it: %s", (_, tree, doc, expected) => {
    expect(evaluateDependsOn(toDependsOn(tree, scope), doc)).toBe(expected);
  });

  it("reads a parent's field from the parent", () => {
    const text = toDependsOn(
      group([leaf("parent.is_return", "equals", "Yes")]),
      scope
    );
    expect(evaluateDependsOn(text, { is_return: 0 }, { is_return: 1 })).toBe(
      true
    );
  });
});
