import { describe, expect, it } from "vitest";
import { ROW_ID, identify, rowKey } from "../rowIdentity";

describe("rowIdentity", () => {
  it("prefers the server name over a minted id", () => {
    expect(rowKey({ name: "abc", [ROW_ID]: "row-1" })).toBe("abc");
  });

  it("mints an id only for a row that has neither", () => {
    const saved = { name: "abc" };
    expect(identify(saved)).toEqual({ name: "abc" });

    const fresh: Record<string, any> = {};
    identify(fresh);
    expect(fresh[ROW_ID]).toBeTruthy();
  });

  it("leaves an already-identified row alone", () => {
    const row = { [ROW_ID]: "row-1" };
    identify(row);
    expect(row[ROW_ID]).toBe("row-1");
  });

  it("mints distinct ids", () => {
    const a: Record<string, any> = {};
    const b: Record<string, any> = {};
    identify(a);
    identify(b);
    expect(a[ROW_ID]).not.toBe(b[ROW_ID]);
  });

  it("never mints a `name`, which would make the insert a silent update", () => {
    const fresh: Record<string, any> = {};
    identify(fresh);
    expect(fresh.name).toBeUndefined();
  });
});
