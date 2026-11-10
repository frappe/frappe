import { beforeEach, describe, expect, it } from "vitest";
import { clearDataCache, feedDocumentWrite, readCachedDocument, takeTicket } from "../index";
import { DOCTYPE, NEW, OLD, doc, readList, readRecord, readSomeParts } from "./helpers";

const COLUMNS = {
  _assign: '["ann@example.com"]',
  _user_tags: "urgent",
  _liked_by: '["ann@example.com"]',
  _seen: '["ann@example.com"]',
};

function cachedDoc() {
  return readCachedDocument(DOCTYPE, "A")!.doc;
}

beforeEach(() => {
  clearDataCache();
  readList({ fields: ["name", "modified", ...Object.keys(COLUMNS)] }, [doc("A", OLD, COLUMNS)]);
});

describe("a record read", () => {
  it("keeps the list-only columns its reply leaves out", () => {
    readSomeParts(doc("A", OLD), { permissions: { read: 1 } });
    expect(cachedDoc()).toMatchObject(COLUMNS);
  });

  it("keeps them when the reply is newer", () => {
    readSomeParts(doc("A", NEW), { permissions: { read: 1 } });
    expect(cachedDoc()).toMatchObject({ ...COLUMNS, modified: NEW });
  });

  it("writes _assign and _user_tags from the parts of the same reply", () => {
    readRecord(doc("A", OLD), { assignments: [{ user: "bo@example.com" }], tags: ["billing"] });
    expect(cachedDoc()).toMatchObject({
      _assign: '["bo@example.com"]',
      _user_tags: "billing",
      _liked_by: COLUMNS._liked_by,
      _seen: COLUMNS._seen,
    });
  });
});

describe("the seen part", () => {
  it("writes _seen as the server does, with the reader added", () => {
    readRecord(doc("A", OLD), { seen: ["ann@example.com", "zoë@example.com"] });
    expect(cachedDoc()._seen).toBe('["ann@example.com", "zo\\u00eb@example.com"]');
  });

  it("is never held as a part", () => {
    readRecord(doc("A", OLD), { seen: ["ann@example.com"] });
    expect(readCachedDocument(DOCTYPE, "A")!.parts).not.toHaveProperty("seen");
  });

  it("sets _seen on a record no list read first", () => {
    clearDataCache();
    readRecord(doc("A", OLD), { seen: ["me@example.com"] });
    expect(cachedDoc()._seen).toBe('["me@example.com"]');
  });

  it("adds the reader to a row that read _seen without them", () => {
    readList({ fields: ["name", "modified", "_seen"] }, [doc("A", OLD, { _seen: "" })]);
    readRecord(doc("A", OLD), { seen: ["me@example.com"] });
    expect(cachedDoc()._seen).toBe('["me@example.com"]');
  });
});

describe("a save", () => {
  it("keeps the list-only columns, and _seen unchanged", () => {
    readRecord(doc("A", OLD), { assignments: [{ user: "ann@example.com" }], tags: ["urgent"] });
    feedDocumentWrite(takeTicket(), DOCTYPE, doc("A", NEW, { title: "Saved" }));
    expect(cachedDoc()).toMatchObject({ ...COLUMNS, title: "Saved", modified: NEW });
  });
});
