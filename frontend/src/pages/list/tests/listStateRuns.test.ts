// The list acts that set what the list shows and which rows are selected, and the facts `state()` reads.
import { describe, expect, it, vi } from "vitest";
import { ActInvalid } from "@/acts/dispatcher";
import { listFacts, select, setFilters, setSort, type ListSchema } from "../listStateRuns";

const FIELDS = [
  { fieldname: "customer", label: "Customer", fieldtype: "Link", options: "Customer" },
  { fieldname: "status", label: "Status", fieldtype: "Select", options: "Draft\nPaid" },
  { fieldname: "grand_total", label: "Grand Total", fieldtype: "Currency" },
  { fieldname: "is_return", label: "Is Return", fieldtype: "Check" },
  { fieldname: "secret", label: "Secret", fieldtype: "Data" },
];

function listPage(names = ["SINV-1", "SINV-2", "SINV-3"]) {
  const renderer = { settled: vi.fn(async () => {}), total: vi.fn(() => 42), select: vi.fn() };
  const page = {
    doctype: "Sales Invoice",
    filters: [] as any[],
    sort: [] as any[],
    selection: [] as string[],
    rows: names.map((name) => ({ name, title: `Title of ${name}`, customer: "Ann" })),
    meta: { fields: FIELDS, title_field: "title" },
  };
  return { list: { page, renderer: () => renderer } as any, page, renderer };
}

const schema: ListSchema = { meta: () => listPage().page.meta, readable: (fieldname) => fieldname !== "secret" };

describe("list.set_filters", () => {
  it("replaces the filters with the triples, waits for the rows, and answers the total and the rows", async () => {
    const { list, page, renderer } = listPage();

    const answer = await setFilters(list, schema, { filters: [["status", "=", "Paid"], ["grand_total", ">", 100]] });

    expect(page.filters.map(({ fieldname, operator, value }) => [fieldname, operator, value])).toEqual([
      ["status", "equals", "Paid"],
      ["grand_total", ">", 100],
    ]);
    expect(renderer.settled).toHaveBeenCalled();
    expect(answer).toEqual({
      total: 42,
      rows: [
        { name: "SINV-1", title: "Title of SINV-1" },
        { name: "SINV-2", title: "Title of SINV-2" },
        { name: "SINV-3", title: "Title of SINV-3" },
      ],
    });
  });

  it("clears the filters with an empty list", async () => {
    const { list, page } = listPage();
    page.filters = [{ fieldname: "status" }];

    await setFilters(list, schema, { filters: [] });

    expect(page.filters).toEqual([]);
  });

  it("takes `like` in either case and shows the bare text, as the filter bar does", async () => {
    const { list, page } = listPage();

    await setFilters(list, schema, { filters: [["customer", "like", "%ann%"], ["status", "NOT LIKE", "bob"]] });

    expect(page.filters.map(({ operator, value }) => [operator, value])).toEqual([["like", "ann"], ["not like", "bob"]]);
  });

  it("reads != on a Check as the opposite boolean", async () => {
    const { list, page } = listPage();

    await setFilters(list, schema, { filters: [["is_return", "!=", true]] });

    expect(page.filters[0]).toMatchObject({ fieldname: "is_return", operator: "equals", value: "No" });
  });

  it("turns a Check's 1 or 0 into the boolean the filter reads", async () => {
    const { list, page } = listPage();

    await setFilters(list, schema, { filters: [["is_return", "=", 1]] });

    expect(page.filters[0]).toMatchObject({ fieldname: "is_return", operator: "equals", value: "Yes" });
  });

  it.each([
    ["an unknown field", [["nope", "=", 1]], "nope is not a field this list can filter on"],
    ["a field the reader cannot see", [["secret", "=", "x"]], "secret is not a field this list can filter on"],
    ["an unknown operator", [["status", "contains", "x"]], "contains is not an operator"],
    ["a triple of the wrong size", [["status", "="]], "must be [fieldname, operator, value]"],
    ["in with a scalar", [["status", "in", "Paid"]], "in takes a list of values"],
    ["between with one value", [["grand_total", "between", [1]]], "between takes a list of two values"],
    ["an object value", [["status", "=", { a: 1 }]], "takes one text, number or boolean value"],
    ["a Check with a text operator", [["is_return", "like", "x"]], "is a checkbox; use = or !="],
    ["a Check with a value that is no boolean", [["is_return", "=", "maybe"]], "send true or false"],
    ["an empty value", [["status", "=", ""]], "needs a value"],
    ["an empty list", [["status", "in", []]], "needs at least one value"],
    ["two conditions on one field", [["grand_total", ">", 1], ["grand_total", "<", 5]], "use between for a range"],
  ])("refuses %s as invalid and changes nothing", async (_name, filters, reason) => {
    const { list, page } = listPage();
    page.filters = ["kept"] as any;

    await expect(setFilters(list, schema, { filters })).rejects.toThrow(ActInvalid);
    await expect(setFilters(list, schema, { filters })).rejects.toThrow(reason);
    expect(page.filters).toEqual(["kept"]);
  });

  it("names the first fields to use, and how many more, not all of a long list", async () => {
    const { list, page } = listPage();
    page.meta.fields = Array.from({ length: 40 }, (_, i) => ({ fieldname: `f${i}`, label: `F${i}`, fieldtype: "Data" })) as any;
    const text = await setFilters(list, { ...schema, meta: () => page.meta }, { filters: [["nope", "=", 1]] }).catch((error) => error.message);

    expect(text).toContain("f0, f1");
    expect(text).toMatch(/and \d+ more/);
    expect(text).not.toContain("f39");
  });

  it("fails plainly while the list has no fields yet", async () => {
    const { list } = listPage();

    await expect(setFilters(list, { ...schema, meta: () => null }, { filters: [] })).rejects.toThrow("has not loaded");
  });
});

describe("list.set_sort", () => {
  it("replaces the sort, in the order given, and answers the rows", async () => {
    const { list, page, renderer } = listPage();

    const answer = await setSort(list, schema, { sort: [{ fieldname: "grand_total", direction: "desc" }, { fieldname: "creation", direction: "asc" }] });

    expect(page.sort).toEqual([{ fieldname: "grand_total", direction: "desc" }, { fieldname: "creation", direction: "asc" }]);
    expect(renderer.settled).toHaveBeenCalled();
    expect(answer.total).toBe(42);
  });

  it("clears the sort with an empty list", async () => {
    const { list, page } = listPage();
    page.sort = [{ fieldname: "name", direction: "asc" }];

    await setSort(list, schema, { sort: [] });

    expect(page.sort).toEqual([]);
  });

  it.each([
    ["an unknown field", [{ fieldname: "nope", direction: "asc" }], "nope is not a field this list can sort on"],
    ["a field the reader cannot see", [{ fieldname: "secret", direction: "asc" }], "secret is not a field"],
    ["a bad direction", [{ fieldname: "name", direction: "up" }], 'direction must be "asc" or "desc"'],
  ])("refuses %s as invalid", async (_name, sort, reason) => {
    const { list, page } = listPage();

    await expect(setSort(list, schema, { sort })).rejects.toThrow(ActInvalid);
    await expect(setSort(list, schema, { sort })).rejects.toThrow(reason);
    expect(page.sort).toEqual([]);
  });
});

describe("list.select", () => {
  it("replaces the selection with the named rows, each once", async () => {
    const { list, renderer } = listPage();

    expect(await select(list, ["SINV-2", "SINV-1", "SINV-2"])).toEqual({ selected: ["SINV-2", "SINV-1"] });
    expect(renderer.select).toHaveBeenCalledWith(["SINV-2", "SINV-1"]);
  });

  it("names every row that is not loaded, and selects nothing", async () => {
    const { list, renderer } = listPage();

    await expect(select(list, ["SINV-1", "SINV-9", "SINV-8"])).rejects.toThrow(/not loaded rows: SINV-9, SINV-8/);
    await expect(select(list, ["SINV-9"])).rejects.toThrow(ActInvalid);
    expect(renderer.select).not.toHaveBeenCalled();
  });
});

describe("the list's state facts", () => {
  it("gives filters as REST v2 triples, the sort, the selection and the first 20 rows", () => {
    const names = Array.from({ length: 30 }, (_, index) => `SINV-${index}`);
    const { list, page } = listPage(names);
    page.filters = [{ field: FIELDS[1], fieldname: "status", operator: "equals", value: "Paid" }, { fieldname: "customer", operator: "like", value: "" }];
    page.sort = [{ fieldname: "modified", direction: "desc", extra: 1 }];
    page.selection = ["SINV-1"];

    const facts = listFacts(list, schema);

    expect(facts).toMatchObject({
      doctype: "Sales Invoice",
      filters: [["status", "=", "Paid"]],
      sort: [{ fieldname: "modified", direction: "desc" }],
      selected: ["SINV-1"],
    });
    expect(facts.rows).toHaveLength(20);
    expect(facts.rows[0]).toEqual({ name: "SINV-0", title: "Title of SINV-0" });
  });

  it("titles a row by its name when it has no title, and cuts a long title", () => {
    const { list, page } = listPage(["A", "B"]);
    page.rows = [{ name: "A" }, { name: "B", title: "x".repeat(300) }] as typeof page.rows;

    const [first, second] = listFacts(list, schema).rows;

    expect(first).toEqual({ name: "A", title: "A" });
    expect(second.title).toHaveLength(101);
  });
});
