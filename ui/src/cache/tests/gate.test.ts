import { beforeEach, describe, expect, it } from "vitest";
import {
  clearDataCache,
  feedDelete,
  feedDocumentWrite,
  readCachedDocument,
  readCachedList,
  readCachedRows,
  takeTicket,
} from "../index";
import { DOCTYPE, MIDDLE, NEW, OLD, doc, readList, readRecord } from "./helpers";

const query = { fields: ["name", "title"] };

beforeEach(() => {
  clearDataCache();
  readList(query, [doc("A", OLD, { title: "a" }), doc("B", OLD, { title: "b" })]);
});

describe("the write gate", () => {
  it("drops only the saved document's row from a list reply sent before the save", () => {
    const listTicket = takeTicket();
    feedDocumentWrite(takeTicket(), DOCTYPE, doc("A", MIDDLE, { title: "saved" }));
    readList(
      query,
      [doc("A", NEW, { title: "stale" }), doc("B", NEW, { title: "b2" })],
      {},
      listTicket
    );
    expect(readCachedRows(DOCTYPE, query)!.map((row) => row.title)).toEqual(["saved", "b2"]);
  });

  it("keeps a record read sent before a delete dropped after the delete lands", () => {
    const readTicket = takeTicket();
    feedDelete(takeTicket(), DOCTYPE, "A");
    readRecord(doc("A", NEW), {}, readTicket);
    readList(query, [doc("A", NEW), doc("B", NEW)], {}, readTicket);
    expect(readCachedDocument(DOCTYPE, "A")).toBeUndefined();
    expect(readCachedList(DOCTYPE, query)!.names).toEqual(["B"]);
  });

  it("seals a deleted document against a read sent while the delete was in flight", () => {
    const deleteTicket = takeTicket();
    const readTicket = takeTicket();
    feedDelete(deleteTicket, DOCTYPE, "A");
    readRecord(doc("A", NEW), {}, readTicket);
    expect(readCachedDocument(DOCTYPE, "A")).toBeUndefined();
    readRecord(doc("A", NEW));
    expect(readCachedDocument(DOCTYPE, "A")!.complete).toBe(true);
  });

  it("drops a write sent before a write already applied", () => {
    const first = takeTicket();
    feedDocumentWrite(takeTicket(), DOCTYPE, doc("A", NEW, { title: "second" }));
    feedDocumentWrite(first, DOCTYPE, doc("A", MIDDLE, { title: "first" }));
    expect(readCachedDocument(DOCTYPE, "A")!.doc.title).toBe("second");
  });

  it("gates each document on its own", () => {
    const readTicket = takeTicket();
    feedDocumentWrite(takeTicket(), DOCTYPE, doc("B", MIDDLE, { title: "saved" }));
    readRecord(doc("A", NEW, { title: "read" }), {}, readTicket);
    expect(readCachedDocument(DOCTYPE, "A")!.doc.title).toBe("read");
  });

  it("takes increasing tickets across a clear", () => {
    const before = takeTicket();
    clearDataCache();
    expect(takeTicket()).toBeGreaterThan(before);
  });
});

describe("a write", () => {
  it("replaces the doc of an entry and keeps complete and parts", () => {
    readRecord(doc("A", OLD), { tags: ["x"] });
    feedDocumentWrite(takeTicket(), DOCTYPE, doc("A", NEW, { title: "saved" }));
    const entry = readCachedDocument(DOCTYPE, "A")!;
    expect(entry).toMatchObject({ complete: true, parts: { tags: ["x"] } });
    expect(entry.doc).toEqual({ name: "A", modified: NEW, title: "saved" });
  });

  it("stores nothing for a document the cache does not hold", () => {
    feedDocumentWrite(takeTicket(), DOCTYPE, doc("Z", NEW));
    expect(readCachedDocument(DOCTYPE, "Z")).toBeUndefined();
  });

  it("leaves every list's names alone", () => {
    feedDocumentWrite(takeTicket(), DOCTYPE, doc("B", NEW, { title: "moved" }));
    expect(readCachedList(DOCTYPE, query)!.names).toEqual(["A", "B"]);
  });
});
