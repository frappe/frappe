import { beforeEach, describe, expect, it, vi } from "vitest";
import { computed, nextTick, watch } from "vue";
import {
  clearDataCache,
  feedDocumentWrite,
  readCachedDocument,
  readCachedList,
  readCachedRows,
  takeTicket,
} from "../index";
import { DOCTYPE, NEW, OLD, doc, readList, readRecord } from "./helpers";

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

  it("forgets the writes the gate applied", () => {
    const readTicket = takeTicket();
    feedDocumentWrite(takeTicket(), DOCTYPE, doc("A", OLD));
    clearDataCache();
    readRecord(doc("A", NEW), {}, readTicket);
    expect(readCachedDocument(DOCTYPE, "A")).toBeDefined();
  });
});
