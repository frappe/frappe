import { beforeEach, describe, expect, it, vi } from "vitest";
import { computed, nextTick, watch } from "vue";
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

beforeEach(() => clearDataCache());

describe("a reader", () => {
  it("sees a computed over an entry re-run after a feed", () => {
    const title = computed(() => readCachedDocument(DOCTYPE, "A")?.doc.title);
    expect(title.value).toBeUndefined();
    readRecord(doc("A", OLD, { title: "first" }));
    expect(title.value).toBe("first");
    feedDocumentWrite(takeTicket(), DOCTYPE, doc("A", NEW, { title: "saved" }));
    expect(title.value).toBe("saved");
  });

  it("sees a list feed of several rows as one change", async () => {
    readList(query, [doc("A", OLD), doc("B", OLD), doc("C", OLD)]);
    const changed = vi.fn();
    const stop = watch(() => readCachedRows(DOCTYPE, query), changed);
    readList(query, [doc("A", NEW), doc("B", NEW), doc("C", NEW), doc("D", NEW)]);
    await nextTick();
    expect(changed).toHaveBeenCalledTimes(1);
    expect(changed.mock.calls[0][0]).toHaveLength(4);
    stop();
  });

  it("sees one change per reply on a document entry", () => {
    readList(query, [doc("A", OLD)]);
    const changed = vi.fn();
    const stop = watch(() => readCachedDocument(DOCTYPE, "A"), changed, { flush: "sync" });
    readList(query, [doc("A", NEW), doc("B", NEW)]);
    expect(changed).toHaveBeenCalledTimes(1);
    readRecord(doc("A", NEW, { title: "read" }));
    expect(changed).toHaveBeenCalledTimes(2);
    feedDelete(takeTicket(), DOCTYPE, "A");
    expect(changed).toHaveBeenCalledTimes(3);
    stop();
  });

  it("sees one sync change per list reply, and none for a reply that changes nothing", () => {
    readList(query, [doc("A", OLD), doc("B", OLD)]);
    const older = takeTicket();
    const [rows, record] = [vi.fn(), vi.fn()];
    const stops = [
      watch(() => readCachedRows(DOCTYPE, query), rows, { flush: "sync" }),
      watch(() => readCachedDocument(DOCTYPE, "A"), record, { flush: "sync" }),
    ];
    readList(query, [doc("A", NEW), doc("B", NEW), doc("C", NEW)]);
    expect([rows.mock.calls.length, record.mock.calls.length]).toEqual([1, 1]);
    readList(query, [doc("A", MIDDLE), doc("B", MIDDLE)], {}, older);
    readList({ fields: ["name"] }, [doc("Z", OLD)]);
    expect([rows.mock.calls.length, record.mock.calls.length]).toEqual([1, 1]);
    stops.forEach((stop) => stop());
  });
});

describe("clearDataCache", () => {
  it("empties documents and lists", () => {
    readList(query, [doc("A", OLD)]);
    readRecord(doc("B", OLD));
    clearDataCache();
    expect(readCachedDocument(DOCTYPE, "A")).toBeUndefined();
    expect(readCachedDocument(DOCTYPE, "B")).toBeUndefined();
    expect(readCachedList(DOCTYPE, query)).toBeUndefined();
  });

  it("drops every reply to a request sent before it", () => {
    const before = takeTicket();
    clearDataCache();
    readList(query, [doc("A", OLD)]);
    readRecord(doc("B", OLD));
    readRecord(doc("A", NEW), PERMISSIONS, before);
    readList({ fields: ["name"] }, [doc("C", OLD)], {}, before);
    feedDocumentWrite(before, DOCTYPE, doc("B", NEW));
    feedDocsDocument(before, DOCTYPE, doc("B", NEW));
    feedPartWrite(before, DOCTYPE, "B", "tags", ["x"]);
    const [first, second] = [readCachedDocument(DOCTYPE, "A")!, readCachedDocument(DOCTYPE, "B")!];
    expect(first).toMatchObject({ complete: false, doc: { modified: OLD } });
    expect(second).toMatchObject({ doc: { modified: OLD }, parts: PERMISSIONS });
    expect(second.doc).not.toHaveProperty("_user_tags");
    expect(readCachedList(DOCTYPE, { fields: ["name"] })).toBeUndefined();
  });
});
