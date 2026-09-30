import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { ApiError } from "../../api/envelope";
import { clearDataCache, feedDelete, feedReadError, onRecordLeft, takeTicket } from "../index";
import { DOCTYPE, NEW, OLD, doc, readList, readRecord, readSomeParts } from "./helpers";

let left: string[];
let stop: () => void;

beforeEach(() => {
  clearDataCache();
  left = [];
  stop = onRecordLeft((doctype, name) => left.push(`${doctype}:${name}`));
});

afterEach(() => stop());

describe("onRecordLeft", () => {
  it("names the record the 51st record read pushes out", () => {
    for (let index = 1; index <= 51; index++) readRecord(doc(`R${index}`, OLD));
    expect(left).toEqual([`${DOCTYPE}:R1`]);
  });

  it("names a record a list still holds as a row once it is no longer complete", () => {
    readList({}, [doc("R0", OLD)]);
    for (let index = 0; index <= 50; index++) readRecord(doc(`R${index}`, OLD));
    expect(left).toEqual([`${DOCTYPE}:R0`]);
  });

  it("names a deleted record, a refused one and every record at a user change", () => {
    for (const name of ["A", "B", "C", "D"]) readRecord(doc(name, OLD));
    feedDelete(takeTicket(), DOCTYPE, "A");
    feedReadError(takeTicket(), DOCTYPE, "B", new ApiError({ type: "PermissionError" }, 403));
    clearDataCache();
    expect(left).toEqual(["A", "B", "C", "D"].map((name) => `${DOCTYPE}:${name}`));
  });

  it("names a record a newer read with fewer parts replaces", () => {
    readRecord(doc("A", OLD));
    readList({}, [doc("A", NEW)]);
    expect(left).toEqual([`${DOCTYPE}:A`]);
  });

  it("stays quiet while the record stays complete", () => {
    readRecord(doc("A", OLD));
    readRecord(doc("A", NEW));
    readList({}, [doc("A", NEW)]);
    readSomeParts(doc("A", NEW), { tags: [] });
    expect(left).toEqual([]);
  });

  it("stops once the returned function runs", () => {
    readRecord(doc("A", OLD));
    stop();
    feedDelete(takeTicket(), DOCTYPE, "A");
    expect(left).toEqual([]);
  });
});
