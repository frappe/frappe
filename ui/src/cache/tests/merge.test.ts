import { beforeEach, describe, expect, it } from "vitest";
import { clearDataCache, readCachedDocument, readCachedList } from "../index";
import { DOCTYPE, MIDDLE, NEW, OLD, doc, readList, readRecord } from "./helpers";

const query = { fields: ["name", "title"] };

beforeEach(() => clearDataCache());

describe("a list row against the document entry", () => {
  beforeEach(() => {
    readRecord(doc("A", MIDDLE, { title: "saved", status: "Open" }), { tags: ["x"] });
  });

  it("replaces the doc when newer, and makes the entry partial", () => {
    readList(query, [doc("A", NEW, { title: "newer" })]);
    const entry = readCachedDocument(DOCTYPE, "A")!;
    expect(entry.doc).toEqual({ name: "A", modified: NEW, title: "newer" });
    expect(entry.complete).toBe(false);
    expect(entry.parts).toEqual({});
  });

  it("merges its fields when equal, and keeps complete and parts", () => {
    readList(query, [doc("A", MIDDLE, { title: "listed" })]);
    const entry = readCachedDocument(DOCTYPE, "A")!;
    expect(entry.doc).toEqual({ name: "A", modified: MIDDLE, title: "listed", status: "Open" });
    expect(entry.complete).toBe(true);
    expect(entry.parts).toEqual({ tags: ["x"] });
  });

  it("is dropped when older, and the list still names the document", () => {
    readList(query, [doc("A", OLD, { title: "stale" })]);
    expect(readCachedDocument(DOCTYPE, "A")!.doc.title).toBe("saved");
    expect(readCachedList(DOCTYPE, query)!.names).toEqual(["A"]);
  });

  it("is taken as newer by an entry with no modified", () => {
    readList(query, [doc("B", undefined, { title: "bare" })]);
    readList(query, [doc("B", OLD, { title: "dated" })]);
    expect(readCachedDocument(DOCTYPE, "B")!.doc).toEqual({
      name: "B",
      modified: OLD,
      title: "dated",
    });
  });

  it("with no name makes the whole reply feed nothing", () => {
    readList(query, [doc("C", NEW), { title: "nameless", modified: NEW }]);
    expect(readCachedDocument(DOCTYPE, "C")).toBeUndefined();
    expect(readCachedList(DOCTYPE, query)).toBeUndefined();
  });
});

describe("a record read", () => {
  it("keeps the include parts it got, never seen", () => {
    readRecord(doc("A", OLD), { permissions: { read: 1 }, seen: ["me"], link_titles: {} });
    const entry = readCachedDocument(DOCTYPE, "A")!;
    expect(entry.complete).toBe(true);
    expect(entry.parts).toEqual({ permissions: { read: 1 }, link_titles: {} });
  });

  it("is dropped when older than the entry", () => {
    readRecord(doc("A", NEW, { title: "new" }));
    readRecord(doc("A", OLD, { title: "old" }));
    expect(readCachedDocument(DOCTYPE, "A")!.doc.title).toBe("new");
  });

  it("stores a frozen copy, so the caller's reply stays its own", () => {
    const record = doc("A", OLD, { items: [{ qty: 1 }] });
    readRecord(record);
    (record.items as { qty: number }[])[0].qty = 5;
    const entry = readCachedDocument(DOCTYPE, "A")!;
    expect(entry.doc.items).toEqual([{ qty: 1 }]);
    expect(Object.isFrozen(entry)).toBe(true);
    expect(Object.isFrozen((entry.doc.items as object[])[0])).toBe(true);
  });
});

describe("a record read that asks for no parts", () => {
  it("stores nothing for a document the cache does not hold", () => {
    readRecord(doc("A", OLD), {});
    expect(readCachedDocument(DOCTYPE, "A")).toBeUndefined();
  });

  it("leaves a partial entry partial", () => {
    readList(query, [doc("A", OLD, { title: "listed" })]);
    readRecord(doc("A", OLD, { title: "read", status: "Open" }), {});
    const entry = readCachedDocument(DOCTYPE, "A")!;
    expect(entry.complete).toBe(false);
    expect(entry.doc).toEqual({ name: "A", modified: OLD, title: "read", status: "Open" });
  });

  it("replaces a complete entry's doc when newer, keeping complete and parts", () => {
    readRecord(doc("A", OLD, { title: "first" }), { tags: ["x"] });
    readRecord(doc("A", NEW, { title: "second" }), {});
    expect(readCachedDocument(DOCTYPE, "A")).toMatchObject({
      complete: true,
      parts: { tags: ["x"] },
      doc: { modified: NEW, title: "second" },
    });
  });

  it("is dropped when older than the entry", () => {
    readRecord(doc("A", NEW, { title: "new" }));
    readRecord(doc("A", OLD, { title: "old" }), {});
    expect(readCachedDocument(DOCTYPE, "A")!.doc.title).toBe("new");
  });
});
