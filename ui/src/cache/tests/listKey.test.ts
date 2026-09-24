import { describe, expect, it } from "vitest";
import type { ListQuery } from "../../api";
import { listCacheKey } from "../index";

const key = (query: ListQuery, doctype = "ToDo") => listCacheKey(doctype, query);

describe("listCacheKey", () => {
  it("ignores the order of object keys, at any depth", () => {
    expect(
      key({ filters: { status: "Open", owner: { a: 1, b: 2 } }, order_by: "modified desc" })
    ).toBe(key({ order_by: "modified desc", filters: { owner: { b: 2, a: 1 }, status: "Open" } }));
  });

  it("ignores the order and repeats of fields, and whether modified is asked for", () => {
    expect(key({ fields: ["title", "name", "title"] })).toBe(
      key({ fields: ["name", "modified", "title"] })
    );
  });

  it("keeps the order of filter arrays", () => {
    expect(key({ filters: [["status", "=", "Open"]] })).not.toBe(
      key({ filters: [["Open", "=", "status"]] })
    );
  });

  it("ignores start, limit, include and undefined values", () => {
    const bare = key({ filters: { status: "Open" } });
    expect(
      key({ filters: { status: "Open", owner: undefined }, start: 40, limit: 20, include: "count" })
    ).toBe(bare);
    expect(key({ filters: { status: "Open" }, order_by: undefined })).toBe(bare);
  });

  it.each([
    ["doctype", key({}, "Note")],
    ["filters", key({ filters: { status: "Closed" } })],
    ["or_filters", key({ or_filters: { status: "Closed" } })],
    ["order_by", key({ order_by: "creation asc" })],
    ["group_by", key({ group_by: "status" })],
    ["fields", key({ fields: ["name"] })],
  ])("changes with %s", (_, other) => {
    expect(other).not.toBe(key({}));
  });
});
