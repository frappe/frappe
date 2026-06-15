import { describe, expect, it } from "vitest";
import { evaluateDependsOn } from "../dependsOn";

describe("evaluateDependsOn", () => {
  it("treats empty / undefined expressions as no condition (true)", () => {
    expect(evaluateDependsOn(undefined, {})).toBe(true);
    expect(evaluateDependsOn("", {})).toBe(true);
  });

  it("evaluates a bare fieldname by truthiness of doc[fieldname]", () => {
    expect(evaluateDependsOn("status", { status: "Open" })).toBe(true);
    expect(evaluateDependsOn("status", { status: "" })).toBe(false);
    expect(evaluateDependsOn("status", {})).toBe(false);
  });

  it("treats arrays as truthy only when non-empty", () => {
    expect(evaluateDependsOn("items", { items: [1] })).toBe(true);
    expect(evaluateDependsOn("items", { items: [] })).toBe(false);
  });

  it("runs eval: expressions against { doc }", () => {
    expect(evaluateDependsOn("eval:doc.qty > 1", { qty: 5 })).toBe(true);
    expect(evaluateDependsOn("eval:doc.qty > 1", { qty: 0 })).toBe(false);
    expect(
      evaluateDependsOn('eval:doc.status == "Open"', { status: "Open" })
    ).toBe(true);
  });

  it("fails open (returns true) when an eval: expression throws", () => {
    // `doc.nested` is undefined → accessing `.deep` throws a TypeError.
    expect(evaluateDependsOn("eval:doc.nested.deep === 1", {})).toBe(true);
  });

  it("scopes `parent` as a separate binding (desk: { doc, parent })", () => {
    const row = { qty: 0 };
    const parent = { allow_edit: 1 };
    // `doc` is the row, `parent` is the enclosing doc — distinct names.
    expect(evaluateDependsOn("eval:parent.allow_edit == 1", row, parent)).toBe(
      true
    );
    expect(evaluateDependsOn("eval:parent.allow_edit == 0", row, parent)).toBe(
      false
    );
    expect(evaluateDependsOn("eval:doc.qty == 0", row, parent)).toBe(true);
  });

  it("does not merge parent into doc — `doc.x` never falls through to parent", () => {
    // A field only on the parent is invisible to `doc`; reach it via `parent`.
    expect(
      evaluateDependsOn(
        "eval:doc.allow_edit == 1",
        { qty: 0 },
        { allow_edit: 1 }
      )
    ).toBe(false);
  });

  it("defaults `parent` to `doc` (desk top-level: parent === doc)", () => {
    expect(evaluateDependsOn("eval:parent.qty > 1", { qty: 5 })).toBe(true);
    expect(evaluateDependsOn("eval:parent.qty > 1", { qty: 0 })).toBe(false);
  });
});
