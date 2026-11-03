import { describe, expect, it, vi } from "vitest";
import { otherStaleRecord, showStaleRecord } from "../staleRecord";

vi.mock("@/i18n", () => ({
  __: (text: string, args: string[] = []) => text.replace(/\{(\d+)\}/g, (_, i) => args[Number(i)]),
}));

describe("otherStaleRecord", () => {
  it("is null for the page's own record, which keeps Save's dialog", () => {
    const own = { doctype: "Sales Invoice", name: "SINV-1" };
    expect(otherStaleRecord(own, "Sales Invoice", "SINV-1")).toBeNull();
  });

  it("is null when the error names no record", () => {
    expect(otherStaleRecord(undefined, "Sales Invoice", "SINV-1")).toBeNull();
  });

  it("returns another record, or a hidden one", () => {
    const linked = { doctype: "Payment Entry", name: "PE-1" };
    expect(otherStaleRecord(linked, "Sales Invoice", "SINV-1")).toBe(linked);
    expect(otherStaleRecord({ doctype: "Sales Invoice", name: "SINV-2" }, "Sales Invoice", "SINV-1"))
      .toEqual({ doctype: "Sales Invoice", name: "SINV-2" });
    expect(otherStaleRecord({ hidden: true }, "Sales Invoice", "SINV-1")).toEqual({ hidden: true });
  });
});

describe("showStaleRecord", () => {
  it("names the record and opens it, and does not offer a reload", async () => {
    const confirm = vi.fn().mockResolvedValue(null);
    const open = vi.fn();
    await showStaleRecord(confirm, { doctype: "Payment Entry", name: "PE-1" }, open);

    const options = confirm.mock.calls[0][0];
    expect(options.message).toContain("Payment Entry PE-1");
    expect(options.actions.map((action: { label: string }) => action.label)).toEqual([
      "Open PE-1",
      "Close",
    ]);
    options.actions[0].onClick();
    expect(open).toHaveBeenCalledWith("Payment Entry", "PE-1");
  });

  it("names nothing for a record the reader cannot read", async () => {
    const confirm = vi.fn().mockResolvedValue(null);
    await showStaleRecord(confirm, { hidden: true }, vi.fn());

    const options = confirm.mock.calls[0][0];
    expect(options.actions.map((action: { label: string }) => action.label)).toEqual(["Close"]);
    expect(options.message).not.toMatch(/PE-|Payment/);
  });
});
