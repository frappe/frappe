// What the page makes of a failed save: the message it shows and the fields the reader would lose.
import { describe, expect, it, vi } from "vitest";
import {
  changedFields,
  cancelledError,
  codeErrorsError,
  confirmConflict,
  confirmRecordConflict,
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
    expect(confirm.mock.calls[0][0].message).toContain("Reload to see their version");
    expect(confirm.mock.calls[1][0].message).toContain("Use theirs, or keep editing");
  });
});

describe("confirmRecordConflict", () => {
  const ask = async (changed: string[], act?: "submit" | "cancel") => {
    const confirm = vi.fn().mockResolvedValue(true);
    await confirmRecordConflict(confirm, "Ada", changed, act);
    return confirm.mock.calls[0][0];
  };

  it("keeps Save's text for a save", async () => {
    const options = await ask([]);
    expect(options.message).toContain("cannot be saved over theirs");
  });

  it("gives a clean Submit its own text", async () => {
    const options = await ask([], "submit");
    expect(options.message).toBe(
      "Ada saved this record after you opened it. Reload to see their version before you submit.",
    );
  });

  it("gives a clean Cancel its own text", async () => {
    const options = await ask([], "cancel");
    expect(options.message).toBe(
      "Ada saved this record after you opened it. Reload to see their version before you cancel.",
    );
  });

  it("keeps Save's text for a Submit or Cancel with unsaved changes", async () => {
    for (const act of ["submit", "cancel"] as const) {
      const options = await ask(["Status"], act);
      expect(options.message).toContain("your changes to Status cannot be saved over theirs");
    }
  });

  it("keeps the dialog's title and buttons", async () => {
    const options = await ask([], "submit");
    expect(options).toMatchObject({
      title: "Saved by someone else",
      confirmLabel: "Reload and lose my changes",
      cancelLabel: "Keep editing",
    });
  });

  it("returns whether the reader chose to reload", async () => {
    expect(await confirmRecordConflict(vi.fn().mockResolvedValue(false), "Ada", [], "submit")).toBe(false);
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
    expect(shownInDialog(cancelledError())).toBe(true);
    expect(shownInDialog(new Error("Amount is required"))).toBe(false);
    expect(shownInDialog(null)).toBe(false);
  });
});
