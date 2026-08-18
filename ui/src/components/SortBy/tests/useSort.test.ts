import { describe, expect, it } from "vitest";
// useSort owns the sort order and the `order_by` string a host fetches with.
// Self-contained (no Meta), so it's exercised directly.
import { useSort } from "../useSort";

describe("useSort", () => {
  it("starts empty with an empty order_by string", () => {
    const { by, orderBy } = useSort();
    expect(by.value).toEqual([]);
    expect(orderBy.value).toBe("");
  });

  it("serializes a sort to a Frappe order_by string", () => {
    const { by, orderBy } = useSort();
    by.value = [{ fieldname: "modified", direction: "desc" }];
    expect(orderBy.value).toBe("modified desc");
  });

  it("joins multiple sorts in order", () => {
    const { by, orderBy } = useSort();
    by.value = [
      { fieldname: "status", direction: "asc" },
      { fieldname: "modified", direction: "desc" },
    ];
    expect(orderBy.value).toBe("status asc, modified desc");
  });
});
