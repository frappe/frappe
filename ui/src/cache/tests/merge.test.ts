import { beforeEach, describe, expect, it } from "vitest";
import { clearDataCache, readCachedDocument, readCachedList } from "../index";
import {
  ALL_PARTS,
  DOCTYPE,
  MIDDLE,
  NEW,
  OLD,
  doc,
  readList,
  readRecord,
  readSomeParts,
} from "./helpers";

const query = { fields: ["name", "title"] };

function withoutTags(parts: Record<string, unknown>) {
  return Object.fromEntries(Object.entries(parts).filter(([part]) => part !== "tags"));
}

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
    expect(entry.parts).toMatchObject({ tags: ["x"] });
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
    readRecord(doc("A", OLD), { seen: ["me"], link_titles: { x: "X" } });
    const entry = readCachedDocument(DOCTYPE, "A")!;
    expect(entry.complete).toBe(true);
    expect(entry.parts.link_titles).toEqual({ x: "X" });
    expect(entry.parts).not.toHaveProperty("seen");
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

describe("a record read of some parts", () => {
  it("adds them to a list-held entry, which is complete once it holds every part", () => {
    readList(query, [doc("A", OLD)]);
    readSomeParts(doc("A", OLD), { tags: ["x"] });
    const entry = () => readCachedDocument(DOCTYPE, "A");
    expect(entry()).toMatchObject({ complete: false, parts: { tags: ["x"] } });
    readSomeParts(doc("A", OLD), withoutTags(ALL_PARTS));
    expect(entry()).toMatchObject({ complete: true, parts: { tags: ["x"] } });
  });

  it("when newer replaces the parts held, and leaves the entry partial", () => {
    readList(query, [doc("A", OLD)]);
    readRecord(doc("A", OLD), { tags: ["x"] });
    readSomeParts(doc("A", NEW), { tags: ["y"] });
    const entry = readCachedDocument(DOCTYPE, "A")!;
    expect(entry).toMatchObject({ complete: false, parts: { tags: ["y"] } });
  });

  it("stores nothing for a document the cache does not hold", () => {
    readSomeParts(doc("A", OLD), { tags: ["x"] });
    expect(readCachedDocument(DOCTYPE, "A")).toBeUndefined();
  });
});

describe("a record read that asks for no parts", () => {
  it("stores nothing for a document the cache does not hold", () => {
    readSomeParts(doc("A", OLD), {});
    expect(readCachedDocument(DOCTYPE, "A")).toBeUndefined();
  });

  it("leaves a partial entry partial", () => {
    readList(query, [doc("A", OLD, { title: "listed" })]);
    readSomeParts(doc("A", OLD, { title: "read", status: "Open" }), {});
    const entry = readCachedDocument(DOCTYPE, "A")!;
    expect(entry.complete).toBe(false);
    expect(entry.doc).toEqual({ name: "A", modified: OLD, title: "read", status: "Open" });
  });

  it("keeps a complete entry's parts when equal", () => {
    readRecord(doc("A", OLD, { title: "first" }), { tags: ["x"] });
    readSomeParts(doc("A", OLD, { title: "second" }), {});
    expect(readCachedDocument(DOCTYPE, "A")).toMatchObject({
      complete: true,
      parts: { tags: ["x"] },
      doc: { title: "second" },
    });
  });

  it("when newer removes a complete entry that no list names", () => {
    readRecord(doc("A", OLD, { title: "first" }), { tags: ["x"] });
    readSomeParts(doc("A", NEW, { title: "second" }), {});
    expect(readCachedDocument(DOCTYPE, "A")).toBeUndefined();
  });

  it("is dropped when older than the entry", () => {
    readRecord(doc("A", NEW, { title: "new" }));
    readSomeParts(doc("A", OLD, { title: "old" }), {});
    expect(readCachedDocument(DOCTYPE, "A")!.doc.title).toBe("new");
  });
});
