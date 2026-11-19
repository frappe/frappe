// The values `page.cached` keeps for a record: at most 20 keys for each script.
import { beforeEach, describe, expect, it } from "vitest";
import { clearDataCache, feedRecordRead, RECORD_PARTS, takeTicket } from "@framework/ui/cache";
import { keeperFor, keptValue, resetKeptValues } from "../keptValues";

const DOCTYPE = "CRM Deal";
const DOCNAME = "CRM-DEAL-1";

function cacheRecord() {
  const parts = Object.fromEntries(RECORD_PARTS.map((part) => [part, []]));
  const envelope = {
    data: { name: DOCNAME, modified: "2026-09-30 10:00:00" },
    ...parts,
  };
  feedRecordRead(takeTicket(), DOCTYPE, envelope as any, RECORD_PARTS, 1000);
}

function keep(source: string, from: number, to: number) {
  const keeper = keeperFor(DOCTYPE, DOCNAME);
  for (let index = from; index <= to; index++) keeper(source, `key${index}`, index);
}

const kept = (source: string, index: number) =>
  keptValue(DOCTYPE, DOCNAME, source, `key${index}`)?.value;

beforeEach(() => {
  clearDataCache();
  resetKeptValues();
  cacheRecord();
});

describe("kept page.cached values", () => {
  it("drop the least recently used key at a script's 21st key", () => {
    keep("credit", 1, 21);
    expect(kept("credit", 1)).toBeUndefined();
    expect(kept("credit", 2)).toBe(2);
    expect(kept("credit", 21)).toBe(21);
  });

  it("count a read of a kept value as a use", () => {
    keep("credit", 1, 20);
    expect(kept("credit", 1)).toBe(1);
    keep("credit", 21, 21);
    expect(kept("credit", 1)).toBe(1);
    expect(kept("credit", 2)).toBeUndefined();
  });

  it("limit each script on its own", () => {
    keep("credit", 1, 20);
    keep("other", 1, 20);
    expect(kept("credit", 1)).toBe(1);
    expect(kept("other", 20)).toBe(20);
  });
});
