import { describe, expect, it } from "vitest";
import {
  expressionOperators,
  isFilterExpression,
  normalizeCheckValues,
  summarizeCondition,
  toExpression,
  toFilters,
} from "../conditions";

const fields = [
  { fieldname: "status", fieldtype: "Link" },
  { fieldname: "organization", fieldtype: "Data" },
  { fieldname: "job_title", fieldtype: "Data" },
  { fieldname: "annual_revenue", fieldtype: "Currency" },
  { fieldname: "converted", fieldtype: "Check" },
];

describe("building a condition from filters", () => {
  it("quotes text and leaves numbers bare", () => {
    expect(toExpression([["status", "=", "Qualified"]], fields)).toBe(
      'doc.status == "Qualified"'
    );
    expect(toExpression([["annual_revenue", ">=", "50000"]], fields)).toBe(
      "doc.annual_revenue >= 50000"
    );
  });

  it("writes membership, presence and contains without builtins", () => {
    expect(toExpression([["status", "in", ["New", "Open"]]], fields)).toBe(
      'doc.status in ["New", "Open"]'
    );
    expect(toExpression([["organization", "is", "set"]], fields)).toBe(
      '(doc.organization or "") != ""'
    );
    expect(toExpression([["job_title", "like", "%Head%"]], fields)).toBe(
      '"head" in (doc.job_title or "").lower()'
    );
  });

  it("joins every filter with and", () => {
    expect(
      toExpression(
        [
          ["status", "=", "Qualified"],
          ["converted", "=", 0],
        ],
        fields
      )
    ).toBe('doc.status == "Qualified" and doc.converted == 0');
  });

  it("escapes quotes in values", () => {
    expect(toExpression([["organization", "=", 'A "big" co']], fields)).toBe(
      'doc.organization == "A \\"big\\" co"'
    );
  });
});

describe("reading a condition back into filters", () => {
  it("keeps mixed conjunctions in the expression editor", () => {
    const conditions = [
      ["status", "in", ["New", "Open"]],
      "and",
      ["job_title", "not like", "intern"],
      "or",
      ["organization", "is", "not set"],
    ];
    const expression = toExpression(conditions, fields);

    expect(toFilters(expression)).toBeNull();
  });

  it("keeps a group together", () => {
    const conditions = [
      ["status", "=", "Open"],
      "and",
      [["source", "=", "Website"], "or", ["source", "=", "Referral"]],
    ];
    const expression = toExpression(conditions, fields);

    expect(expression).toBe(
      'doc.status == "Open" and (doc.source == "Website" or doc.source == "Referral")'
    );
    expect(toFilters(expression)).toEqual(conditions);
  });

  it("accepts the single quotes a Python-authored condition uses", () => {
    expect(toFilters("doc.status in ['New', 'Open']")).toEqual([
      ["status", "in", ["New", "Open"]],
    ]);
    expect(toFilters("doc.status == 'Qualified'")).toEqual([
      ["status", "=", "Qualified"],
    ]);
  });

  it("refuses anything filters cannot express", () => {
    expect(
      isFilterExpression('doc.email.split("@")[-1] not in ["a.com"]')
    ).toBe(false);
    expect(
      isFilterExpression('context.get("event", {}).get("x") == "Matched"')
    ).toBe(false);
    expect(toFilters('doc.status == "Qualified"')).not.toBeNull();
  });

  it("treats an empty condition as no filters", () => {
    expect(toFilters("")).toEqual([]);
    expect(isFilterExpression("")).toBe(true);
  });

  it("accepts an empty membership list while a filter row is incomplete", () => {
    expect(toFilters("doc.status in []")).toEqual([["status", "in", []]]);
    expect(toFilters("doc.status not in []")).toEqual([
      ["status", "not in", []],
    ]);
  });
});

describe("refusing expressions it cannot represent", () => {
  const SENIORITY =
    '"chief" in (doc.job_title or "").lower() or "head" in (doc.job_title or "").lower()';
  const TOTAL = '(context["steps"].get("a", {}).get("delta", 0)) >= 45';

  it("reads an or-chain as two contains rows", () => {
    expect(toFilters(SENIORITY)).toEqual([
      ["job_title", "like", "chief"],
      "or",
      ["job_title", "like", "head"],
    ]);
    expect(toExpression(toFilters(SENIORITY), fields)).toBe(SENIORITY);
  });

  it("rejects expressions that are not a plain field comparison", () => {
    expect(toFilters(TOTAL)).toBeNull();
    expect(toFilters('doc.email.split("@")[-1] == "acme.com"')).toBeNull();
    expect(toFilters("doc.status == doc.other")).toBeNull();
  });

  it("still accepts the plain forms it writes", () => {
    expect(toFilters('doc.status == "Open"')).toEqual([
      ["status", "=", "Open"],
    ]);
    expect(toFilters("doc.score >= 45")).toEqual([["score", ">=", 45]]);
  });
});

describe("summaries", () => {
  it("reads a condition as a sentence", () => {
    expect(summarizeCondition('doc.source == "Website"')).toBe(
      "Source is Website"
    );
    expect(summarizeCondition('(doc.organization or "") != ""')).toBe(
      "Organization is set"
    );
    expect(summarizeCondition('doc.status in ["New", "Open"]')).toBe(
      "Status is one of New, Open"
    );
    expect(summarizeCondition('"head" in (doc.job_title or "").lower()')).toBe(
      "Job title contains head"
    );
  });
});

describe("safe condition editing", () => {
  it("compiles Check selections to document values without converting text fields", () => {
    expect(toExpression([["converted", "=", "Yes"]], fields)).toBe(
      "doc.converted == 1"
    );
    expect(toExpression([["converted", "=", "No"]], fields)).toBe(
      "doc.converted == 0"
    );
    expect(toExpression([["organization", "=", "Yes"]], fields)).toBe(
      'doc.organization == "Yes"'
    );
  });

  it("normalizes Check controls and stored filters with metadata", () => {
    const values = [["converted", "=", 1], "and", [["converted", "=", 0]]];
    const display = [
      ["converted", "=", "Yes"],
      "and",
      [["converted", "=", "No"]],
    ];
    expect(normalizeCheckValues(values, fields, true)).toEqual(display);
    expect(normalizeCheckValues(display, fields)).toEqual(values);
    expect(
      normalizeCheckValues([["organization", "=", "Yes"]], fields)
    ).toEqual([["organization", "=", "Yes"]]);
  });

  it("retains commas and empty members inside quoted membership values", () => {
    const rows = [["status", "in", ["North, America", "Europe", ""]]];
    expect(toFilters(toExpression(rows, fields))).toEqual(rows);
    expect(toFilters("doc.status in ['North, America', 'Europe']")).toEqual([
      ["status", "in", ["North, America", "Europe"]],
    ]);
  });

  it("keeps escaped Python literals in Expression mode", () => {
    for (const expression of [
      String.raw`doc.organization == "line\nnext"`,
      String.raw`doc.organization == "\u0041"`,
      String.raw`doc.organization == "a\\b"`,
    ]) {
      expect(toFilters(expression)).toBeNull();
      expect(isFilterExpression(expression)).toBe(false);
    }
    expect(toExpression([["organization", "=", "line\nnext"]], fields)).toBe(
      String.raw`doc.organization == "line\nnext"`
    );
  });

  it("withholds operators the step expression compiler cannot evaluate", () => {
    expect(expressionOperators("Date").map(({ value }) => value)).not.toContain(
      "between"
    );
    expect(
      expressionOperators("Datetime").map(({ value }) => value)
    ).not.toContain("between");
    for (const type of ["Int", "Float", "Currency", "Percent", "Duration"]) {
      const operators = expressionOperators(type).map(({ value }) => value);
      expect(operators).not.toContain("like");
      expect(operators).not.toContain("not like");
    }
    expect(expressionOperators("Data").map(({ value }) => value)).toContain(
      "like"
    );
    expect(
      isFilterExpression(
        '"10" in (doc.annual_revenue or "").lower()',
        "doc",
        fields
      )
    ).toBe(false);
  });

  it("uses the explicit document scope in every nested clause", () => {
    const rows = [
      ["status", "=", "Open"],
      "and",
      [["organization", "is", "set"], "or", ["status", "in", ["Qualified"]]],
    ];
    const expression = toExpression(rows, fields, "target");
    expect(expression).toBe(
      'target.status == "Open" and ((target.organization or "") != "" or target.status in ["Qualified"])'
    );
    expect(toFilters(expression, "target")).toEqual(rows);
    expect(isFilterExpression('doc.status == "Open"', "target")).toBe(false);
    expect(isFilterExpression('target.status == "Open"', "doc")).toBe(false);
    expect(toFilters('target.organization == "doc.status"', "target")).toEqual([
      ["organization", "=", "doc.status"],
    ]);
  });
});
