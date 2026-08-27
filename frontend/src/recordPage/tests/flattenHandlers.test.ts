// The authored shape (ticket 54) against the flat keyspace the engine dispatches
// on: what a script writes, and what `registerRecordPage` stores.
import { beforeEach, describe, expect, it, vi } from "vitest";

import { flattenHandlers } from "../flattenHandlers";
import { registerRecordPage, registrationsFor, resetRegistry } from "../registry";

const noop = () => {};

describe("flattenHandlers", () => {
  it("flattens a table's block onto dotted keys", () => {
    const qty = () => {};
    const flat = flattenHandlers(
      { onRefresh: noop, products: { onAdd: noop, qty } },
      "host",
      "CRM Deal",
    );
    expect(Object.keys(flat)).toEqual([
      "onRefresh",
      "products.onAdd",
      "products.qty",
    ]);
    // The author's function, not a wrapper: the dispatch path is unchanged.
    expect(flat["products.qty"]).toBe(qty);
  });

  // Nothing about `page.rows`, the handle or the arguments rule changed with the
  // spelling, so a script written against the merged dotted keys still runs.
  it("passes a flat dotted key straight through", () => {
    const flat = flattenHandlers({ "products.qty": noop }, "host", "CRM Deal");
    expect(Object.keys(flat)).toEqual(["products.qty"]);
  });

  it("names a nested value that is not a block of handlers", () => {
    const warnings = vi.spyOn(console, "warn").mockImplementation(() => {});
    const flat = flattenHandlers(
      { products: { qty: 3 } as any, totals: "yes" as any },
      "page-script:A",
      "CRM Deal",
    );
    expect(Object.keys(flat)).toEqual([]);
    expect(warnings).toHaveBeenCalledTimes(2);
    expect(String(warnings.mock.calls[0][0])).toContain(
      "page-script:A.products on CRM Deal",
    );
    warnings.mockRestore();
  });

  // Vacuously a block of functions, and so the one authoring mistake the check
  // would otherwise wave through.
  it("names an empty block", () => {
    const warnings = vi.spyOn(console, "warn").mockImplementation(() => {});
    expect(Object.keys(flattenHandlers({ products: {} }, "host", "CRM Deal"))).toEqual([]);
    expect(String(warnings.mock.calls[0][0])).toContain("empty block");
    warnings.mockRestore();
  });

  // Both spellings are accepted, so one can land on the other — last wins, but
  // not in silence.
  it("names a key written twice", () => {
    const warnings = vi.spyOn(console, "warn").mockImplementation(() => {});
    const nested = () => {};
    const flat = flattenHandlers(
      { "products.qty": noop, products: { qty: nested } },
      "host",
      "CRM Deal",
    );
    expect(flat["products.qty"]).toBe(nested);
    expect(String(warnings.mock.calls[0][0])).toContain("written twice");
    warnings.mockRestore();
  });

  // The one moment the engine can say what to write instead. Advice, not a
  // refusal: `add` is a legal child fieldname, which is the whole point.
  it("names the retired dotted spelling", () => {
    const warnings = vi.spyOn(console, "warn").mockImplementation(() => {});
    flattenHandlers({ "products.add": noop }, "host", "CRM Deal");
    expect(String(warnings.mock.calls[0][0])).toContain(
      "products: { onAdd() {} }",
    );
    warnings.mockRestore();
  });

  // `<parent>_add` is an ordinary parent fieldname; accusing one would be a
  // warning that lies.
  it("does not accuse an underscore fieldname", () => {
    const warnings = vi.spyOn(console, "warn").mockImplementation(() => {});
    flattenHandlers({ products_add: noop }, "host", "CRM Deal");
    expect(warnings).not.toHaveBeenCalled();
    warnings.mockRestore();
  });

  // 51's lesson, one level down: a keyspace argument about fieldnames says
  // nothing about strings that were never fieldnames.
  it("cannot be made to write onto Object.prototype", () => {
    const flat = flattenHandlers(
      { ["__proto__"]: noop, evil: { ["__proto__"]: noop } } as any,
      "host",
      "CRM Deal",
    );
    expect(Object.getPrototypeOf(flat)).toBe(null);
    expect(Object.getPrototypeOf({})).toBe(Object.prototype);
    expect(flat["__proto__"]).toBe(noop);
    expect(flat["evil.__proto__"]).toBe(noop);
  });

  // A doctype may have a field called `constructor`, and an inherited hit would
  // dispatch that field's commit to `Object.prototype`.
  it("answers only with what the author wrote", () => {
    const flat = flattenHandlers({ onRefresh: noop }, "host", "CRM Deal");
    expect(flat["constructor"]).toBeUndefined();
    expect(flat["toString"]).toBeUndefined();
  });
});

describe("registerRecordPage", () => {
  beforeEach(() => resetRegistry());

  // The one choke point both file scripts and stored scripts pass through.
  it("stores the flattened keys", () => {
    registerRecordPage("CRM Deal", { products: { onAdd: noop } });
    expect(Object.keys(registrationsFor("CRM Deal")[0].handlers)).toEqual([
      "products.onAdd",
    ]);
  });
});
