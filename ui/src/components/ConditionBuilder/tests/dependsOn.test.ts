import { describe, expect, it, vi } from "vitest";
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

/**
 * Records to evaluate a condition on, each with its parent. A table is always
 * a list; a new record leaves a Check with no default, and `__islocal`, unset.
 */
const SAMPLES: [Record<string, unknown>, Record<string, unknown>][] = [
  [{ items: [], docstatus: 0, __islocal: 1 }, {}],
  [{ is_pos: 0, items: [], docstatus: 0 }, { is_return: 0 }],
  [
    {
      is_pos: 0,
      customer: "",
      status: "",
      grand_total: 0,
      remarks: null,
      items: [],
      docstatus: 0,
    },
    { is_return: 0 },
  ],
  [
    {
      is_pos: 1,
      customer: "A",
      status: "Paid",
      grand_total: 1000,
      remarks: "x",
      posting_date: "2026-06-01",
      uom: "Nos",
      stock_uom: "Nos",
      items: [{}],
      docstatus: 1,
      __islocal: 1,
    },
    { is_return: 1 },
  ],
  [
    {
      is_pos: 0,
      customer: "B",
      status: "Unpaid",
      grand_total: -10,
      remarks: "y",
      posting_date: "2027-01-01",
      uom: "Box",
      stock_uom: "Nos",
      items: [],
      docstatus: 2,
    },
    { is_return: 0 },
  ],
];

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
    "a range from no value, as two comparisons",
    'eval:"" <= doc.remarks && doc.remarks <= "m"',
    group([leaf("remarks", ">=", ""), leaf("remarks", "<=", "m")]),
  ],
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

  // What it reads must still mean what the author wrote, empty fields included.
  it.each(WRITTEN)("writes %s with the meaning it had", (_, text) => {
    // Desk v1's global, which desk v2's evaluator does not define.
    vi.stubGlobal("in_list", (list: unknown[], item: unknown) =>
      list.includes(item)
    );
    const written = toDependsOn(fromDependsOn(text, scope)!, scope);
    for (const [doc, parent] of SAMPLES) {
      expect(evaluateDependsOn(written, doc, parent)).toBe(
        evaluateDependsOn(text, doc, parent)
      );
    }
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
    ["a Check against true", "eval:doc.is_pos === true"],
    ["a Check against text, strictly", 'eval:doc.is_pos === "1"'],
    ["a number against text, strictly", 'eval:doc.grand_total === "5"'],
    ["a number against no value", 'eval:doc.grand_total == ""'],
    ["text against a number", "eval:doc.remarks === 5"],
    ["text ordered by a number", "eval:doc.remarks > 5"],
    ["a status as text, strictly", 'eval:doc.docstatus === "1"'],
    ["a value that reads as a reference", 'eval:doc.remarks === "eval:x"'],
    ["a listed value with a comma", 'eval:["a,b", "c"].includes(doc.remarks)'],
    ["a listed value with a space", 'eval:[" a"].includes(doc.remarks)'],
    ["a listed empty value", 'eval:["", "Paid"].includes(doc.status)'],
    ["a listed number for text", "eval:[5].includes(doc.remarks)"],
    ["a listed status as text", 'eval:["1"].includes(doc.docstatus)'],
    ["a status range", "eval:1 <= doc.docstatus && doc.docstatus <= 2"],
    [
      "a length range",
      "eval:1 <= doc.remarks.length && doc.remarks.length <= 3",
    ],
    ["a text range of numbers", "eval:1 <= doc.remarks && doc.remarks <= 5"],
    ["a Check range", "eval:0 <= doc.is_pos && doc.is_pos <= 1"],
    ["a table compared", "eval:doc.items === 1"],
    ["a table listed", 'eval:["x"].includes(doc.items)'],
    ["a length of text", "eval:doc.remarks.length > 0"],
    ["includes on a field that may be empty", 'eval:doc.remarks.includes("x")'],
    ["an octal number", "eval:doc.grand_total === 010"],
    ["a Check against 0", "eval:doc.is_pos === 0"],
    ["a Check unequal to 0", "eval:doc.is_pos != 0"],
    ["a Check against false", "eval:doc.is_pos == false"],
    ["a new record against 0", "eval:doc.__islocal == 0"],
    ["two fields, loosely", "eval:doc.grand_total == doc.remarks"],
    ["two fields unequal, loosely", "eval:doc.uom != doc.stock_uom"],
    ["text inside a Check", 'eval:String(doc.is_pos ?? "").includes("1")'],
    ["text inside a status", 'eval:String(doc.docstatus ?? "").includes("1")'],
    ["a number or no text", 'eval:(doc.grand_total || "").includes("5")'],
    ["no text inside", 'eval:!(doc.remarks || "").includes("")'],
    ["a reference inside", 'eval:(doc.remarks || "").includes("eval:doc.uom")'],
    ["space before eval", "  eval:doc.remarks"],
    ["a bare name with a newline", "remarks\n"],
    ["a line break inside text", 'eval:doc.remarks === "a\nb"'],
    ["eval with nothing", "eval:"],
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

  it("writes a value that looks like a reference as text", () => {
    const tree = group([
      leaf("remarks", "equals", "eval:parent.x || (globalThis.pwned = 1)"),
      leaf("customer", "in", ["eval:doc.y || 1"]),
      leaf("remarks", "equals", "eval:doc.items"),
    ]);
    expect(toDependsOn(tree, scope)).toBe(
      'eval:doc.remarks === "eval:parent.x || (globalThis.pwned = 1)" && ' +
        '["eval:doc.y || 1"].includes(doc.customer) && ' +
        'doc.remarks === "eval:doc.items"'
    );
  });

  it("drops a number row with no number", () => {
    const tree = group([
      leaf("grand_total", ">", ""),
      leaf("grand_total", "equals", "abc"),
      leaf("grand_total", "between", ["eval:doc.grand_total", 5]),
      leaf("customer", "is", "set"),
    ]);
    expect(toDependsOn(tree, scope)).toBe("customer");
  });

  it("writes typed list and range items as text, never as references", () => {
    const tree = group([
      leaf("customer", "in", "eval:doc.uom, x"),
      leaf("remarks", "between", ["eval:doc.uom", "z"]),
    ]);
    expect(toDependsOn(tree, scope)).toBe(
      'eval:["eval:doc.uom", "x"].includes(doc.customer) && ' +
        '("eval:doc.uom" <= doc.remarks && doc.remarks <= "z")'
    );
  });

  it("refuses an operator it has no code for", () => {
    const tree = group([leaf("customer", "descendants of", "x")]);
    expect(() => toDependsOn(tree, scope)).toThrow();
  });

  it("refuses a fieldname that is not a name", () => {
    const tree = group([leaf("x); alert(1); (", "is", "set")]);
    expect(() => toDependsOn(tree, scope)).toThrow();
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
      "text inside a Check",
      group([leaf("is_pos", "like", "0")]),
      { is_pos: 1 },
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
