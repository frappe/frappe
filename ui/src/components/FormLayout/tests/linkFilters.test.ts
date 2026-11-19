import { describe, expect, it } from "vitest";
import { mergeLinkFilters, resolveLinkFilters } from "../linkFilters";
import { resolveFieldConditionals } from "../resolveLayout";

const STORED = JSON.stringify([
  ["Customer", "disabled", "=", 0],
  ["Customer", "company", "=", "eval:doc.company"],
]);

describe("resolveLinkFilters", () => {
  it("reads fixed values and resolves eval: against the record", () => {
    expect(resolveLinkFilters(STORED, { company: "Acme" })).toEqual({
      disabled: ["=", 0],
      company: ["=", "Acme"],
    });
  });

  it("reads parent. on a child row", () => {
    const stored = [["Warehouse", "company", "=", "eval:parent.company"]];
    expect(resolveLinkFilters(stored, {}, { company: "Acme" })).toEqual({
      company: ["=", "Acme"],
    });
  });

  it("sends null for an unset field and leaves out a failing expression", () => {
    const stored = [
      ["Customer", "company", "=", "eval:doc.company"],
      ["Customer", "territory", "=", "eval:doc.nope.deeper"],
    ];
    expect(resolveLinkFilters(stored, {})).toEqual({ company: ["=", null] });
    expect(resolveLinkFilters([stored[1]], {})).toBeUndefined();
  });

  it("is undefined when there are none or the JSON is broken", () => {
    expect(resolveLinkFilters(undefined, {})).toBeUndefined();
    expect(resolveLinkFilters("[]", {})).toBeUndefined();
    expect(resolveLinkFilters("[[", {})).toBeUndefined();
  });
});

describe("mergeLinkFilters", () => {
  it("replaces a script's list rows for the same field, as v1 does", () => {
    const script = [
      ["Customer", "company", "=", "Script"],
      ["customer_group", "=", "Retail"],
      ["Contact", "company", "=", "Other"],
    ];
    expect(mergeLinkFilters(script, { company: ["=", "Acme"] }, "Customer")).toEqual([
      ["customer_group", "=", "Retail"],
      ["Contact", "company", "=", "Other"],
      ["company", "=", "Acme"],
    ]);
  });
});

describe("resolveFieldConditionals filters", () => {
  const field = {
    fieldname: "customer",
    fieldtype: "Link",
    options: "Customer",
    filters: { customer_group: "Retail", company: ["=", "Script"] },
    linkFilters: STORED,
  };

  it("merges the DocField's filters over a script's, from the live doc", () => {
    expect(resolveFieldConditionals(field, { company: "Acme" }).filters).toEqual({
      customer_group: "Retail",
      company: ["=", "Acme"],
      disabled: ["=", 0],
    });
  });

  it("passes a script's filters through when the DocField has none", () => {
    const plain = { ...field, linkFilters: undefined };
    expect(resolveFieldConditionals(plain, {}).filters).toBe(plain.filters);
  });
});
