import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick, ref } from "vue";

// frappe-ui is unresolvable in unit tests, so stand in a resource that records the
// params of every fetch and lets a test set the data it would have returned.
const h = vi.hoisted(() => ({ resources: [] as any[] }));
vi.mock("frappe-ui", async () => {
  const { reactive } = await import("vue");
  return {
    createResource: (options: {
      makeParams: () => Record<string, unknown>;
    }) => {
      const resource = reactive({
        data: null as unknown,
        loading: false,
        calls: [] as Record<string, unknown>[],
        fetch() {
          resource.calls.push(options.makeParams());
        },
      });
      h.resources.push(resource);
      return resource;
    },
  };
});

import { useGroupByData } from "../useGroupByData";
import type { GroupBySettings } from "../types";

const BY_STATUS: GroupBySettings = {
  fields: ["status"],
  aggregates: [{ function: "count" }],
};

beforeEach(() => {
  h.resources.length = 0;
});

describe("useGroupByData", () => {
  it("fetches one row per group and the group keys for the total", () => {
    useGroupByData("CRM Deal", BY_STATUS, { converted: 0 });
    const [groups, keys] = h.resources;

    expect(groups.calls).toEqual([
      {
        doctype: "CRM Deal",
        filters: { converted: 0 },
        fields: ["status", { COUNT: "name", as: "_aggregate_0" }],
        group_by: "status",
        order_by: "_aggregate_0 desc",
        limit_page_length: 20,
      },
    ]);
    expect(keys.calls).toEqual([
      {
        doctype: "CRM Deal",
        filters: { converted: 0 },
        fields: ["status"],
        group_by: "status",
        limit_page_length: 0,
      },
    ]);
  });

  it("fetches nothing for an ungrouped list", () => {
    const data = useGroupByData("CRM Deal", null, {});
    expect(h.resources.every((r) => r.calls.length === 0)).toBe(true);
    expect(data.rows.value).toEqual([]);
  });

  it("reads rows and counts from the fetched data", () => {
    const data = useGroupByData("CRM Deal", BY_STATUS, {});
    const [groups, keys] = h.resources;
    expect(data.hasCounts.value).toBe(false);

    groups.data = [{ status: "Won", _aggregate_0: 3 }];
    keys.data = [{ status: "Won" }, { status: "Lost" }];

    expect(data.rows.value).toEqual([{ status: "Won", _aggregate_0: 3 }]);
    expect(data.rowCount.value).toBe(1);
    expect(data.totalCount.value).toBe(2);
    expect(data.hasCounts.value).toBe(true);
  });

  it("grows the page on loadMore and starts over when the filters change", async () => {
    const filters = ref<Record<string, unknown>>({});
    const data = useGroupByData("CRM Deal", BY_STATUS, filters);
    const [groups] = h.resources;

    data.loadMore();
    expect(groups.calls.at(-1).limit_page_length).toBe(40);

    filters.value = { status: "Won" };
    await nextTick();
    expect(groups.calls.at(-1)).toMatchObject({
      filters: { status: "Won" },
      limit_page_length: 20,
    });
  });

  it("refetches with the new page length", async () => {
    const data = useGroupByData("CRM Deal", BY_STATUS, {});
    const [groups] = h.resources;

    data.pageLength.value = 50;
    await nextTick();
    expect(groups.calls.at(-1).limit_page_length).toBe(50);
  });
});
