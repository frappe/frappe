import { beforeEach, describe, expect, it } from "vitest";
import { clearDataCache, feedPartWrite, readCachedDocument, takeTicket } from "../index";
import { DOCTYPE, OLD, doc, readList, readRecord } from "./helpers";

const assignments = [
  { user: "ann@example.com", priority: "Medium" },
  { user: "bo@example.com", priority: "High" },
];

function applyPart(name: string, part: string, value: unknown) {
  feedPartWrite(takeTicket(), DOCTYPE, name, part, value);
}

beforeEach(() => clearDataCache());

describe("a part on a complete entry", () => {
  beforeEach(() => readRecord(doc("A", OLD), { assignments: [], tags: [] }));

  it("sets the part and _assign as the server writes it", () => {
    applyPart("A", "assignments", assignments);
    const entry = readCachedDocument(DOCTYPE, "A")!;
    expect(entry.parts.assignments).toEqual(assignments);
    expect(entry.doc._assign).toBe('["ann@example.com", "bo@example.com"]');
    expect(entry.doc.modified).toBe(OLD);
  });

  it("sets the part and _user_tags as the server writes it", () => {
    applyPart("A", "tags", ["urgent", "billing"]);
    const entry = readCachedDocument(DOCTYPE, "A")!;
    expect(entry.parts.tags).toEqual(["urgent", "billing"]);
    expect(entry.doc._user_tags).toBe("urgent,billing");
  });

  it("writes an empty string when the last assignment or tag goes", () => {
    applyPart("A", "assignments", []);
    applyPart("A", "tags", []);
    expect(readCachedDocument(DOCTYPE, "A")!.doc).toMatchObject({ _assign: "", _user_tags: "" });
  });

  it("escapes a non-ASCII user id the way Python's json.dumps does", () => {
    applyPart("A", "assignments", [{ user: "zoë@example.com" }]);
    expect(readCachedDocument(DOCTYPE, "A")!.doc._assign).toBe('["zo\\u00eb@example.com"]');
  });

  it("sets any other part without touching the doc", () => {
    const before = readCachedDocument(DOCTYPE, "A")!.doc;
    applyPart("A", "follows", true);
    const entry = readCachedDocument(DOCTYPE, "A")!;
    expect(entry.parts.follows).toBe(true);
    expect(entry.doc).toBe(before);
  });
});

describe("a part on a partial entry", () => {
  beforeEach(() => readList({ fields: ["name"] }, [doc("A", OLD)]));

  it("sets _assign and _user_tags but holds no part", () => {
    applyPart("A", "assignments", assignments);
    applyPart("A", "tags", ["urgent"]);
    const entry = readCachedDocument(DOCTYPE, "A")!;
    expect(entry.doc).toMatchObject({
      _assign: '["ann@example.com", "bo@example.com"]',
      _user_tags: "urgent",
    });
    expect(entry.parts).toEqual({});
    expect(entry.complete).toBe(false);
  });
});

describe("a part for a document the cache does not hold", () => {
  it("stores nothing", () => {
    applyPart("Z", "tags", ["urgent"]);
    expect(readCachedDocument(DOCTYPE, "Z")).toBeUndefined();
  });
});
