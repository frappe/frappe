// What the page makes of a failed save: the message it shows and the fields the reader would lose.
import { describe, expect, it } from "vitest";
import { changedFields, conflictError, SAVE_CONFLICT, stripTags } from "../saveResponse";

const FIELDS = [
  { fieldname: "status", fieldtype: "Select", label: "Status" },
  { fieldname: "probability", fieldtype: "Percent", label: "Probability" },
  { fieldname: "notes", fieldtype: "Text" },
];

describe("stripTags", () => {
  it("reads a msgprint's HTML as text, with a break as a space", () => {
    expect(stripTags("<p>Amount is required<br>for a won deal</p>")).toBe(
      "Amount is required for a won deal"
    );
    expect(stripTags("plain")).toBe("plain");
  });
});

describe("changedFields", () => {
  it("names the changed fields by label, in meta order, and skips private keys", () => {
    const saved = { status: "Open", probability: 50, notes: "", _user_tags: "" };
    const doc = { status: "Won", probability: 100, notes: "", _user_tags: "x" };
    expect(changedFields(doc, saved, FIELDS)).toEqual(["Status", "Probability"]);
  });

  it("falls back to the fieldname without a label, and lists keys the meta lacks last", () => {
    const saved = { notes: "a", extra: 1 };
    const doc = { notes: "b", extra: 2 };
    expect(changedFields(doc, saved, FIELDS)).toEqual(["notes", "extra"]);
  });

  it("compares by value, so a re-ordered child row list still counts", () => {
    const saved = { items: [{ name: "a" }] };
    const doc = { items: [{ name: "a" }] };
    expect(changedFields(doc, saved, [])).toEqual([]);
    expect(changedFields({ items: [] }, saved, [])).toEqual(["items"]);
  });
});

describe("conflictError", () => {
  it("carries the name the save path suppresses its message under", () => {
    expect(conflictError().name).toBe(SAVE_CONFLICT);
  });
});
