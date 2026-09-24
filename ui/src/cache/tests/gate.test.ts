import { beforeEach, describe, expect, it } from "vitest";
import {
  clearDataCache,
  feedDelete,
  feedDocsDocument,
  feedDocumentWrite,
  feedPartWrite,
  readCachedDocument,
  readCachedList,
  readCachedRows,
  takeTicket,
} from "../index";
import { DOCTYPE, MIDDLE, NEW, OLD, PERMISSIONS, doc, readList, readRecord } from "./helpers";

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
    feedDelete(DOCTYPE, "A");
    readRecord(doc("A", NEW), PERMISSIONS, readTicket);
    readList(query, [doc("A", NEW), doc("B", NEW)], PERMISSIONS, readTicket);
    expect(readCachedDocument(DOCTYPE, "A")).toBeUndefined();
    expect(readCachedList(DOCTYPE, query)!.names).toEqual(["B"]);
  });

  it("seals a deleted document against a read sent while the delete was in flight", () => {
    const readTicket = takeTicket();
    feedDelete(DOCTYPE, "A");
    readRecord(doc("A", NEW), PERMISSIONS, readTicket);
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
    readRecord(doc("A", NEW, { title: "read" }), PERMISSIONS, readTicket);
    expect(readCachedDocument(DOCTYPE, "A")!.doc.title).toBe("read");
  });

  it("keeps a refused row's name in the list, unless the document was deleted", () => {
    const listTicket = takeTicket();
    feedDocumentWrite(takeTicket(), DOCTYPE, doc("Z", NEW));
    feedDelete(DOCTYPE, "B");
    readList(query, [doc("A", NEW), doc("B", NEW), doc("Z", NEW)], {}, listTicket);
    expect(readCachedList(DOCTYPE, query)!.names).toEqual(["A", "Z"]);
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

describe("a part write", () => {
  it("drops a record or list read sent before it", () => {
    readRecord(doc("A", OLD, { title: "a" }), { tags: [] });
    const readTicket = takeTicket();
    feedPartWrite(takeTicket(), DOCTYPE, "A", "tags", ["urgent"]);
    readRecord(doc("A", OLD, { _user_tags: "" }), { tags: [] }, readTicket);
    readList(query, [doc("A", OLD, { _user_tags: "" }), doc("B", OLD)], {}, readTicket);
    const entry = readCachedDocument(DOCTYPE, "A")!;
    expect(entry.doc._user_tags).toBe("urgent");
    expect(entry.parts.tags).toEqual(["urgent"]);
    expect(readCachedList(DOCTYPE, query)!.names).toEqual(["A", "B"]);
  });
});

describe("a document of a reply's docs", () => {
  beforeEach(() => readRecord(doc("A", MIDDLE, { title: "saved" }), { tags: ["x"] }));

  it("applies when a save moved modified forward, keeping complete and parts", () => {
    feedDocsDocument(takeTicket(), DOCTYPE, doc("A", NEW, { title: "method" }));
    expect(readCachedDocument(DOCTYPE, "A")).toMatchObject({
      complete: true,
      parts: { tags: ["x"] },
      doc: { modified: NEW, title: "method" },
    });
  });

  it.each([
    ["the same", MIDDLE],
    ["an older", OLD],
  ])("with %s modified holds unsaved values and is dropped", (_, modified) => {
    feedDocsDocument(takeTicket(), DOCTYPE, doc("A", modified, { title: "unsaved" }));
    expect(readCachedDocument(DOCTYPE, "A")!.doc.title).toBe("saved");
  });

  it("goes through the gate", () => {
    const methodTicket = takeTicket();
    feedDocumentWrite(takeTicket(), DOCTYPE, doc("A", NEW, { title: "second" }));
    feedDocsDocument(methodTicket, DOCTYPE, doc("A", "2026-09-04 10:00:00.000000"));
    expect(readCachedDocument(DOCTYPE, "A")!.doc.title).toBe("second");
  });
});
