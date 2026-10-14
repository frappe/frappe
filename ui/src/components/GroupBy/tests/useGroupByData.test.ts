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

import { GROUP_COUNT_CAP, useGroupByData } from "../useGroupByData";
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
        limit_page_length: 1000,
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

  it("fetches the totals over every record only when totals are on", () => {
    useGroupByData("CRM Deal", BY_STATUS, {});
    expect(h.resources[2].calls).toEqual([]);

    h.resources.length = 0;
    const data = useGroupByData(
      "CRM Deal",
      { ...BY_STATUS, showTotals: true },
      { converted: 0 }
    );
    const totals = h.resources[2];
    expect(totals.calls).toEqual([
      {
        doctype: "CRM Deal",
        filters: { converted: 0 },
        fields: [{ COUNT: "name", as: "_aggregate_0" }],
        limit_page_length: 1,
      },
    ]);
    totals.data = [{ _aggregate_0: 690 }];
    expect(data.totals.value).toEqual({ _aggregate_0: 690 });
  });

  it("keeps the loaded pages when only a column width changes", async () => {
    const groupBy = ref<GroupBySettings>({ ...BY_STATUS });
    const data = useGroupByData("CRM Deal", groupBy, {});
    const [groups] = h.resources;
    data.loadMore();
    const calls = groups.calls.length;

    groupBy.value = { ...groupBy.value, widths: { status: "300px" } };
    await nextTick();
    expect(groups.calls.length).toBe(calls);

    groupBy.value = {
      ...groupBy.value,
      sort: [{ fieldname: "status", direction: "asc" }],
    };
    await nextTick();
    expect(groups.calls.at(-1)).toMatchObject({
      order_by: "status asc",
      limit_page_length: 20,
    });
  });

  it("marks the total as a floor when the group keys hit the cap", () => {
    const data = useGroupByData("CRM Deal", BY_STATUS, {});
    const keys = h.resources[1];
    keys.data = Array.from({ length: GROUP_COUNT_CAP }, (_, i) => ({
      status: i,
    }));
    expect(data.totalCount.value).toBe(GROUP_COUNT_CAP);
    expect(data.totalCapped.value).toBe(true);
  });
});
