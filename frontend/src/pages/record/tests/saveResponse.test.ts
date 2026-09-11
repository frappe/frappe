// A failed save's response, read the two ways the page acts on it.
import { describe, expect, it } from "vitest";
import {
  changedFields,
  conflictError,
  isTimestampMismatch,
  SAVE_CONFLICT,
  serverMessage,
} from "../saveResponse";

const FIELDS = [
  { fieldname: "status", fieldtype: "Select", label: "Status" },
  { fieldname: "probability", fieldtype: "Percent", label: "Probability" },
  { fieldname: "notes", fieldtype: "Text" },
];

describe("isTimestampMismatch", () => {
  it("reads the exception class the server names", () => {
    expect(isTimestampMismatch({ exc_type: "TimestampMismatchError" })).toBe(true);
    expect(isTimestampMismatch({ exc_type: "ValidationError" })).toBe(false);
    expect(isTimestampMismatch(null)).toBe(false);
  });
});

describe("serverMessage", () => {
  it("unwraps the first msgprint from the doubly encoded list", () => {
    const body = {
      _server_messages: JSON.stringify([
        JSON.stringify({ message: "Amount is required", title: "Message" }),
        JSON.stringify({ message: "Second" }),
      ]),
    };
    expect(serverMessage(body)).toBe("Amount is required");
  });

  it("reads a msgprint's HTML as text", () => {
    const body = {
      _server_messages: JSON.stringify([
        JSON.stringify({ message: "<b>Amount</b> is required<br>for a won deal" }),
      ]),
    };
    expect(serverMessage(body)).toBe("Amount is required for a won deal");
  });

  it("answers nothing for a body with no messages or a broken one", () => {
    expect(serverMessage({})).toBeUndefined();
    expect(serverMessage({ _server_messages: "nope" })).toBeUndefined();
    expect(serverMessage(null)).toBeUndefined();
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
