// What the page makes of a failed save: the message it shows and the fields the reader would lose.
import { describe, expect, it, vi } from "vitest";
import {
  changedFields,
  codeErrorsError,
  confirmConflict,
  conflictError,
  SAVE_CONFLICT,
  shownInDialog,
  stripTags,
} from "../saveResponse";

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

  it("does not name a table whose rows another save only restamped", () => {
    const row = (modified: string) => ({ name: "a", parentfield: "items", qty: 1, modified });
    const saved = { items: [row("2026-10-01 11:00:00")] };
    expect(changedFields({ items: [row("2026-10-01 10:00:00")] }, saved, [])).toEqual([]);
  });
});

describe("confirmConflict", () => {
  it("keeps the record page's Reload wording unless the caller names the button", async () => {
    const confirm = vi.fn().mockResolvedValue(true);

    expect(await confirmConflict(confirm, "Ada", ["Status"])).toBe(true);
    await confirmConflict(confirm, "Ada", ["Status"], "Use their Status");

    expect(confirm.mock.calls.map(([options]) => options.confirmLabel)).toEqual([
      "Reload and lose my changes",
      "Use their Status",
    ]);
  });
});

describe("conflictError", () => {
  it("carries the name the save path suppresses its message under", () => {
    expect(conflictError().name).toBe(SAVE_CONFLICT);
  });
});

describe("shownInDialog", () => {
  it("is true for a conflict and for code errors, which a dialog has told the reader", () => {
    expect(shownInDialog(conflictError())).toBe(true);
    expect(shownInDialog(codeErrorsError("Line 3"))).toBe(true);
    expect(shownInDialog(new Error("Amount is required"))).toBe(false);
    expect(shownInDialog(null)).toBe(false);
  });
});
