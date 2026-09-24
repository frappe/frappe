import { beforeEach, describe, expect, it } from "vitest";
import type { DocumentRecord, ListEnvelope } from "../../api";
import { DataCache } from "../dataCache";
import { listCacheKey } from "../listKey";
import { ALL_PARTS, DOCTYPE, MIDDLE, NEW, OLD, doc } from "./helpers";

let cache: DataCache;

const listQuery = (index: number) => ({ filters: { owner: `user${index}` } });

/** Sends a request, feeds its reply and settles it. */
function answered(feed: (ticket: number) => void) {
  const ticket = cache.takeTicket();
  feed(ticket);
  cache.settleTicket(ticket);
}

function readRecord(record: DocumentRecord, ticket: number) {
  cache.recordRead(ticket, DOCTYPE, { data: record, ...ALL_PARTS }, Object.keys(ALL_PARTS));
}

function readList(index: number, names: string[], ticket: number) {
  const envelope = { data: names.map((name) => doc(name, OLD)), has_next_page: false };
  cache.listRead(ticket, DOCTYPE, listQuery(index), envelope as ListEnvelope<DocumentRecord>);
}

function readManyRecords(prefix: string, count: number) {
  for (let index = 1; index <= count; index++) {
    answered((ticket) => readRecord(doc(`${prefix}${index}`, OLD), ticket));
  }
}

beforeEach(() => {
  cache = new DataCache();
});

describe("state kept for entries that left", () => {
  it("is gone once no request is in flight", () => {
    for (let index = 1; index <= 30; index++) {
      answered((ticket) => readList(index, [`L${index}`], ticket));
      cache.rows(listCacheKey(DOCTYPE, listQuery(index)));
    }
    for (let index = 1; index <= 60; index++) {
      answered((ticket) => readRecord(doc(`R${index}`, OLD), ticket));
      answered((ticket) => cache.documentWrite(ticket, DOCTYPE, doc(`R${index}`, MIDDLE)));
    }
    for (let index = 1; index <= 5; index++) {
      answered((ticket) => cache.delete(ticket, DOCTYPE, `D${index}`));
      answered((ticket) => cache.documentWrite(ticket, DOCTYPE, doc(`X${index}`, NEW)));
    }
    expect(cache.sizes()).toEqual({
      documents: 70,
      lists: 20,
      applied: 50,
      sealed: 0,
      landed: 70,
      listed: 20,
      memo: 20,
    });
  });

  it("still refuses an older reply after a write, until that request settles", () => {
    const older = cache.takeTicket();
    answered((ticket) => readRecord(doc("A", OLD), ticket));
    answered((ticket) => cache.documentWrite(ticket, DOCTYPE, doc("A", MIDDLE)));
    readManyRecords("R", 50);
    expect(cache.document(DOCTYPE, "A")).toBeUndefined();
    readRecord(doc("A", NEW, { title: "stale" }), older);
    expect(cache.document(DOCTYPE, "A")).toBeUndefined();
    cache.settleTicket(older);
    expect(cache.sizes().applied).toBe(0);
  });

  it("keeps a deleted document sealed until an older request settles", () => {
    const older = cache.takeTicket();
    answered((ticket) => readRecord(doc("A", OLD), ticket));
    answered((ticket) => cache.delete(ticket, DOCTYPE, "A"));
    readRecord(doc("A", NEW), older);
    expect(cache.document(DOCTYPE, "A")).toBeUndefined();
    expect(cache.sizes().sealed).toBe(1);
    cache.settleTicket(older);
    expect(cache.sizes()).toMatchObject({ applied: 0, sealed: 0 });
  });

  it("still refuses an older list reply after the list left, until it settles", () => {
    const older = cache.takeTicket();
    answered((ticket) => readList(0, ["A"], ticket));
    for (let index = 1; index <= 20; index++) {
      answered((ticket) => readList(index, [`L${index}`], ticket));
    }
    expect(cache.list(listCacheKey(DOCTYPE, listQuery(0)))).toBeUndefined();
    readList(0, ["stale"], older);
    expect(cache.list(listCacheKey(DOCTYPE, listQuery(0)))).toBeUndefined();
    cache.settleTicket(older);
    expect(cache.sizes().listed).toBe(20);
  });
});
