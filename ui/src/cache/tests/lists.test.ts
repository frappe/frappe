import { beforeEach, describe, expect, it } from "vitest";
import { ApiError } from "../../api/envelope";
import {
  clearDataCache,
  feedDelete,
  feedReadError,
  readCachedDocument,
  readCachedList,
  readCachedRows,
} from "../index";
import { DOCTYPE, NEW, OLD, doc, readList, readRecord } from "./helpers";

const query = { fields: ["name", "title"], order_by: "modified desc" };
const rows = (...names: string[]) => names.map((name) => doc(name, OLD, { title: name }));

beforeEach(() => clearDataCache());

describe("a list read", () => {
  it("replaces the names from start 0", () => {
    readList(query, rows("A", "B", "C"));
    readList({ ...query, start: 0 }, rows("D", "A"));
    expect(readCachedList(DOCTYPE, query)!.names).toEqual(["D", "A"]);
  });

  it("keeps the first N names from start N and puts the reply after them", () => {
    readList(query, rows("A", "B", "C"));
    readList({ ...query, start: 2, limit: 2 }, rows("D", "E"));
    expect(readCachedList(DOCTYPE, query)!.names).toEqual(["A", "B", "D", "E"]);
  });

  it("from start N feeds nothing when the list is not held", () => {
    readList({ ...query, start: 20 }, rows("A"));
    expect(readCachedList(DOCTYPE, query)).toBeUndefined();
    expect(readCachedDocument(DOCTYPE, "A")).toBeUndefined();
  });

  it("from start N feeds nothing when the held list has fewer than N names", () => {
    readList(query, rows("A", "B"));
    readList({ ...query, start: 3 }, rows("E"));
    expect(readCachedList(DOCTYPE, query)!.names).toEqual(["A", "B"]);
    expect(readCachedDocument(DOCTYPE, "E")).toBeUndefined();
  });

  it("from start N appends when the held list has exactly N names", () => {
    readList(query, rows("A", "B"));
    readList({ ...query, start: 2 }, rows("C"));
    expect(readCachedList(DOCTYPE, query)!.names).toEqual(["A", "B", "C"]);
  });

  it("removes a partial entry that no list names any more", () => {
    readList(query, rows("A", "B"));
    readRecord(doc("B", OLD));
    readList(query, rows("C"));
    expect(readCachedDocument(DOCTYPE, "A")).toBeUndefined();
    expect(readCachedDocument(DOCTYPE, "B")!.complete).toBe(true);
  });

  it("takes has_next_page, and keeps the count when the reply has none", () => {
    readList(query, rows("A"), { has_next_page: true, count: 7, count_capped: true });
    readList(query, rows("A"), { has_next_page: false });
    expect(readCachedList(DOCTYPE, query)).toMatchObject({
      hasNextPage: false,
      count: 7,
      countCapped: true,
    });
  });

  it.each([
    ["group_by", { fields: ["status"], group_by: "status" }],
    ["a computed field", { fields: ["name", "count(name) as total"] }],
  ])("with %s feeds nothing", (_, grouped) => {
    readList(grouped, rows("A"));
    expect(readCachedList(DOCTYPE, grouped)).toBeUndefined();
    expect(readCachedDocument(DOCTYPE, "A")).toBeUndefined();
  });

  it("with fields * feeds", () => {
    readList({ fields: ["*"] }, rows("A"));
    expect(readCachedRows(DOCTYPE, { fields: ["*"] })).toEqual(rows("A"));
  });

  it("gives its rows in list order, each from the document entry", () => {
    readList(query, rows("B", "A"));
    readRecord(doc("A", NEW, { title: "read" }));
    expect(readCachedRows(DOCTYPE, query)!.map((row) => row.title)).toEqual(["B", "read"]);
  });
});

describe("a delete", () => {
  it("removes the name from every list and lowers a numeric count", () => {
    const other = { fields: ["name"] };
    readList(query, rows("A", "B"), { count: 2 });
    readList(other, rows("B", "C"), { count: null });
    feedDelete(DOCTYPE, "B");
    expect(readCachedDocument(DOCTYPE, "B")).toBeUndefined();
    expect(readCachedList(DOCTYPE, query)).toMatchObject({ names: ["A"], count: 1 });
    expect(readCachedList(DOCTYPE, other)).toMatchObject({ names: ["C"], count: null });
  });

  it("leaves a capped count alone", () => {
    readList(query, rows("A", "B"), { count: 1000, count_capped: true });
    feedDelete(DOCTYPE, "B");
    expect(readCachedList(DOCTYPE, query)).toMatchObject({ names: ["A"], count: 1000 });
  });

  it("leaves a list that does not name it alone", () => {
    readList(query, rows("A"), { count: 1 });
    feedDelete(DOCTYPE, "B");
    expect(readCachedList(DOCTYPE, query)).toMatchObject({ names: ["A"], count: 1 });
  });
});

describe("a read error", () => {
  it.each([403, 404])("%i removes the document entry and leaves lists alone", (status) => {
    readList(query, rows("A", "B"));
    feedReadError(DOCTYPE, "A", new ApiError({ type: "PermissionError" }, status));
    expect(readCachedDocument(DOCTYPE, "A")).toBeUndefined();
    expect(readCachedList(DOCTYPE, query)!.names).toEqual(["A", "B"]);
    expect(readCachedRows(DOCTYPE, query)!.map((row) => row.name)).toEqual(["B"]);
  });

  it("removes an entry held under the name in another case", () => {
    readRecord(doc("Task-A", OLD));
    feedReadError(DOCTYPE, "task-a", new ApiError({ type: "DoesNotExistError" }, 404));
    expect(readCachedDocument(DOCTYPE, "Task-A")).toBeUndefined();
  });

  it("of another kind keeps the entry", () => {
    readRecord(doc("A", OLD));
    feedReadError(DOCTYPE, "A", new ApiError({ type: "HTTPError" }, 500));
    feedReadError(DOCTYPE, "A", new TypeError("offline"));
    expect(readCachedDocument(DOCTYPE, "A")).toBeDefined();
  });
});
