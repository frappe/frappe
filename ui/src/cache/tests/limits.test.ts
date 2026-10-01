import { beforeEach, describe, expect, it } from "vitest";
import {
  clearDataCache,
  feedDelete,
  feedFieldRead,
  holdDocument,
  readCachedDocument,
  readCachedList,
  takeTicket,
} from "../index";
import { DOCTYPE, MB, NEW, OLD, doc, readList, readRecord, readSomeParts } from "./helpers";

const listQuery = (index: number) => ({ filters: { owner: `user${index}` } });

function readRecords(from: number, to: number) {
  for (let index = from; index <= to; index++) readRecord(doc(`R${index}`, OLD), { tags: [] });
}

beforeEach(() => clearDataCache());

describe("the 50 complete entries", () => {
  it("drop the least recently read at the 51st record read", () => {
    readRecords(1, 51);
    expect(readCachedDocument(DOCTYPE, "R1")).toBeUndefined();
    expect(readCachedDocument(DOCTYPE, "R2")!.complete).toBe(true);
  });

  it("count a second record read as a use", () => {
    readRecords(1, 50);
    readRecord(doc("R1", OLD));
    readRecords(51, 51);
    expect(readCachedDocument(DOCTYPE, "R1")!.complete).toBe(true);
    expect(readCachedDocument(DOCTYPE, "R2")).toBeUndefined();
  });

  it("do not count a record read that asks for no parts as a use", () => {
    readRecords(1, 50);
    readSomeParts(doc("R1", OLD), {});
    readRecords(51, 51);
    expect(readCachedDocument(DOCTYPE, "R1")).toBeUndefined();
  });

  it("do not count a read of some parts as a use", () => {
    readRecords(1, 50);
    readSomeParts(doc("R1", OLD), { tags: ["x"] });
    readRecords(51, 51);
    expect(readCachedDocument(DOCTYPE, "R1")).toBeUndefined();
  });

  it("count a read that completes a partial entry as a use", () => {
    readList(listQuery(0), [doc("R1", OLD)]);
    readRecords(2, 51);
    readSomeParts(doc("R1", OLD), { tags: [] });
    expect(readCachedDocument(DOCTYPE, "R1")!.complete).toBe(false);
    readRecord(doc("R1", OLD));
    readRecords(52, 52);
    expect(readCachedDocument(DOCTYPE, "R1")!.complete).toBe(true);
    expect(readCachedDocument(DOCTYPE, "R2")).toBeUndefined();
  });

  it("keep a dropped entry as partial, without parts, while a list names it", () => {
    readList(listQuery(0), [doc("R1", OLD)]);
    readRecords(1, 51);
    const entry = readCachedDocument(DOCTYPE, "R1")!;
    expect(entry).toMatchObject({ complete: false, parts: {} });
    expect(entry.doc).toEqual(doc("R1", OLD));
  });
});

describe("the 32 MB budget of complete records", () => {
  const readSized = (name: string, size: number, modified = OLD) =>
    readRecord(doc(name, modified), {}, takeTicket(), size * MB);
  const complete = (name: string) => readCachedDocument(DOCTYPE, name)?.complete;

  it("drops the least recently read while their replies add up to more than 32 MB", () => {
    readSized("A", 10);
    readSized("B", 10);
    readSized("C", 10);
    expect([complete("A"), complete("B"), complete("C")]).toEqual([true, true, true]);
    readSized("D", 10);
    expect(readCachedDocument(DOCTYPE, "A")).toBeUndefined();
    expect([complete("B"), complete("C"), complete("D")]).toEqual([true, true, true]);
  });

  it("keeps the record read last though it alone is over the budget, until another is read", () => {
    readSized("A", 1);
    readSized("Huge", 40);
    expect(readCachedDocument(DOCTYPE, "A")).toBeUndefined();
    expect(complete("Huge")).toBe(true);
    readSized("Huge", 40);
    expect(complete("Huge")).toBe(true);
    readSized("B", 1);
    expect(readCachedDocument(DOCTYPE, "Huge")).toBeUndefined();
    expect(complete("B")).toBe(true);
  });

  it("counts a record at the size of the reply that made it complete, not of a later row", () => {
    readSized("A", 20);
    readList({}, [doc("A", OLD, { status: "Open" })]);
    readSomeParts(doc("A", OLD), { tags: ["x"] }, takeTicket(), 0);
    readSized("B", 13);
    expect(complete("A")).toBe(false);
    expect(complete("B")).toBe(true);
  });

  it("counts a newer full read at its own size", () => {
    readSized("A", 20);
    readSized("A", 1, NEW);
    readSized("B", 20);
    expect(complete("A")).toBe(true);
  });

  it("keeps a record it drops as partial, without parts, while a list names it", () => {
    readList({}, [doc("A", OLD)]);
    readSized("A", 20);
    readSized("B", 20);
    expect(readCachedDocument(DOCTYPE, "A")).toMatchObject({ complete: false, parts: {} });
  });
});

describe("the 20 list entries", () => {
  function readLists(from: number, to: number) {
    for (let index = from; index <= to; index++) {
      readList(listQuery(index), [doc(`L${index}`, OLD)]);
    }
  }

  it("drop the least recently read at the 21st list read", () => {
    readLists(1, 21);
    expect(readCachedList(DOCTYPE, listQuery(1))).toBeUndefined();
    expect(readCachedList(DOCTYPE, listQuery(2))).toBeDefined();
  });

  it("count a second list read as a use", () => {
    readLists(1, 20);
    readLists(1, 1);
    readLists(21, 21);
    expect(readCachedList(DOCTYPE, listQuery(1))).toBeDefined();
    expect(readCachedList(DOCTYPE, listQuery(2))).toBeUndefined();
  });

  it("remove with a dropped list the partial entries only it names", () => {
    readList(listQuery(1), [doc("Only", OLD), doc("Shared", OLD), doc("Read", OLD)]);
    readRecord(doc("Read", OLD));
    readList(listQuery(2), [doc("Shared", OLD)]);
    readLists(3, 21);
    expect(readCachedDocument(DOCTYPE, "Only")).toBeUndefined();
    expect(readCachedDocument(DOCTYPE, "Shared")!.complete).toBe(false);
    expect(readCachedDocument(DOCTYPE, "Read")!.complete).toBe(true);
  });
});

describe("the 200 field reads", () => {
  function readFields(from: number, to: number): void {
    for (let index = from; index <= to; index++) {
      feedFieldRead(takeTicket(), DOCTYPE, doc(`F${index}`, OLD, { status: "Open" }));
    }
  }

  it("keep a partial entry that no list names, and make no list entry", () => {
    readFields(1, 1);
    expect(readCachedDocument(DOCTYPE, "F1")).toMatchObject({ complete: false });
    expect(readCachedDocument(DOCTYPE, "F1")!.doc.status).toBe("Open");
    expect(readCachedList(DOCTYPE, { filters: { name: "F1" } })).toBeUndefined();
  });

  it("drop the least recently read at the 201st field read", () => {
    readFields(1, 201);
    expect(readCachedDocument(DOCTYPE, "F1")).toBeUndefined();
    expect(readCachedDocument(DOCTYPE, "F2")).toBeDefined();
  });

  it("count a second field read as a use", () => {
    readFields(1, 200);
    readFields(1, 1);
    readFields(201, 201);
    expect(readCachedDocument(DOCTYPE, "F1")).toBeDefined();
    expect(readCachedDocument(DOCTYPE, "F2")).toBeUndefined();
  });

  it("keep an entry past its list's eviction, and a list's entry past theirs", () => {
    readList(listQuery(0), [doc("F1", OLD), doc("Listed", OLD)]);
    readFields(1, 1);
    for (let index = 1; index <= 20; index++) readList(listQuery(index), []);
    expect(readCachedDocument(DOCTYPE, "F1")).toBeDefined();
    expect(readCachedDocument(DOCTYPE, "Listed")).toBeUndefined();

    readList(listQuery(21), [doc("F2", OLD)]);
    readFields(2, 202);
    expect(readCachedDocument(DOCTYPE, "F2")).toBeDefined();
  });

  it("keep a dropped complete entry as partial while a field read holds it", () => {
    readFields(1, 1);
    readRecord(doc("F1", OLD));
    readRecords(1, 50);
    expect(readCachedDocument(DOCTYPE, "F1")).toMatchObject({ complete: false, parts: {} });
  });

  it("keep an entry past the limit while a field on screen holds it", () => {
    const first = holdDocument(DOCTYPE, "F1");
    const second = holdDocument(DOCTYPE, "F1");
    readFields(1, 201);
    first();
    first();
    expect(readCachedDocument(DOCTYPE, "F1")).toBeDefined();
    second();
    expect(readCachedDocument(DOCTYPE, "F1")).toBeUndefined();
  });

  it("do not keep an entry past a delete", () => {
    readFields(1, 1);
    feedDelete(takeTicket(), DOCTYPE, "F1");
    expect(readCachedDocument(DOCTYPE, "F1")).toBeUndefined();
  });
});

describe("how many lists name a document", () => {
  const first = listQuery(1);
  const second = listQuery(2);
  const held = (...names: string[]) =>
    names.filter((name) => readCachedDocument(DOCTYPE, name) !== undefined);

  it("stays right across replace, append, delete and eviction", () => {
    readList(first, [doc("A", OLD), doc("B", OLD)]);
    readList(second, [doc("B", OLD), doc("C", OLD)]);
    readList(first, [doc("B", OLD), doc("D", OLD)]);
    readList(first, [doc("B", OLD), doc("D", OLD)]);
    expect(held("A", "B", "C", "D")).toEqual(["B", "C", "D"]);
    readList({ ...first, start: 2 }, [doc("E", OLD)]);
    feedDelete(takeTicket(), DOCTYPE, "D");
    expect(readCachedList(DOCTYPE, first)!.names).toEqual(["B", "E"]);
    for (let index = 3; index <= 21; index++) readList(listQuery(index), []);
    expect(readCachedList(DOCTYPE, second)).toBeUndefined();
    expect(held("B", "C", "E")).toEqual(["B", "E"]);
    readList(listQuery(22), []);
    expect(readCachedList(DOCTYPE, first)).toBeUndefined();
    expect(held("B", "E")).toEqual([]);
  });
});
