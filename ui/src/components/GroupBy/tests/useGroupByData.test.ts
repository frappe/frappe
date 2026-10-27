import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick, ref } from "vue";

type AggregateQuery = Parameters<typeof import("../../../api").listAggregates>[1];

// Each read answers with what the test set for its kind: the groups, the group
// keys (limit 1000) or the totals (limit 1).
const h = vi.hoisted(() => ({
  calls: [] as { doctype: string; query: AggregateQuery }[],
  answers: { groups: [], keys: [], totals: [] } as Record<string, unknown[]>,
}));
vi.mock("../../../api", () => ({
  listAggregates: vi.fn(async (doctype: string, query: AggregateQuery) => {
    h.calls.push({ doctype, query });
    return { data: h.answers[kind(query)], has_next_page: false };
  }),
}));

function kind(query: AggregateQuery): "groups" | "keys" | "totals" {
  if (query.limit === 1000) return "keys";
  return query.group_by ? "groups" : "totals";
}

function sent(of: "groups" | "keys" | "totals") {
  return h.calls.filter((call) => kind(call.query) === of).map((call) => call.query);
}

// Lets every pending read land.
const settle = () => new Promise((resolve) => setTimeout(resolve));

import { useGroupByData } from "../useGroupByData";
import type { GroupBySettings } from "../types";

const BY_STATUS: GroupBySettings = {
  fields: ["status"],
  aggregates: [{ function: "count" }],
};

beforeEach(() => {
  h.calls.length = 0;
  h.answers = { groups: [], keys: [], totals: [] };
});

describe("useGroupByData", () => {
  it("reads one row per group and the group keys for the total over listAggregates", () => {
    useGroupByData("Sales Order", BY_STATUS, { docstatus: 1 });

    expect(h.calls.map((call) => call.doctype)).toEqual(["Sales Order", "Sales Order"]);
    expect(sent("groups")).toEqual([
      {
        filters: { docstatus: 1 },
        fields: ["status", { COUNT: "name", as: "_aggregate_0" }],
        group_by: "status",
        order_by: "_aggregate_0 desc, status asc",
        limit: 20,
      },
    ]);
    expect(sent("keys")).toEqual([
      { filters: { docstatus: 1 }, fields: ["status"], group_by: "status", limit: 1000 },
    ]);
  });

  it("fetches nothing for an ungrouped list", () => {
    const data = useGroupByData("Sales Order", null, {});
    data.loadMore();
    expect(h.calls).toEqual([]);
    expect(data.rows.value).toEqual([]);
  });

  it("reads rows and counts from the fetched data", async () => {
    h.answers.groups = [{ status: "Won", _aggregate_0: 3 }];
    h.answers.keys = [{ status: "Won" }, { status: "Lost" }];
    const data = useGroupByData("Sales Order", BY_STATUS, {});
    expect(data.hasCounts.value).toBe(false);
    expect(data.loading.value).toBe(true);

    await settle();
    expect(data.loading.value).toBe(false);
    expect(data.rows.value).toEqual([{ status: "Won", _aggregate_0: 3 }]);
    expect(data.rowCount.value).toBe(1);
    expect(data.totalCount.value).toBe(2);
    expect(data.hasCounts.value).toBe(true);
  });

  it("keeps the latest read when an earlier one lands after it", async () => {
    const { listAggregates } = await import("../../../api");
    let answerFirst!: (rows: unknown) => void;
    vi.mocked(listAggregates).mockImplementationOnce(
      (_, query) =>
        new Promise((resolve) => {
          h.calls.push({ doctype: "Sales Order", query });
          answerFirst = (rows) => resolve({ data: rows, has_next_page: false } as never);
        })
    );
    const filters = ref<Record<string, unknown>>({});
    const data = useGroupByData("Sales Order", BY_STATUS, filters);

    h.answers.groups = [{ status: "Won" }];
    filters.value = { status: "Won" };
    await nextTick();
    await settle();
    answerFirst([{ status: "Lost" }]);
    await settle();
    expect(data.rows.value).toEqual([{ status: "Won" }]);
    expect(data.loading.value).toBe(false);
  });

  it("keeps the last rows when a read fails", async () => {
    const { listAggregates } = await import("../../../api");
    const error = vi.spyOn(console, "error").mockImplementation(() => {});
    h.answers.groups = [{ status: "Won" }];
    const data = useGroupByData("Sales Order", BY_STATUS, {});
    await settle();

    vi.mocked(listAggregates).mockRejectedValueOnce(new Error("offline"));
    data.reload();
    await settle();
    expect(data.rows.value).toEqual([{ status: "Won" }]);
    expect(data.loading.value).toBe(false);
    expect(error).toHaveBeenCalledOnce();
    error.mockRestore();
  });

  it("grows the page on loadMore and starts over when the filters change", async () => {
    const filters = ref<Record<string, unknown>>({});
    const data = useGroupByData("Sales Order", BY_STATUS, filters);

    data.loadMore();
    expect(sent("groups").at(-1)!.limit).toBe(40);

    filters.value = { status: "Won" };
    await nextTick();
    expect(sent("groups").at(-1)).toMatchObject({ filters: { status: "Won" }, limit: 20 });
  });

  it("refetches with the new page length", async () => {
    const data = useGroupByData("Sales Order", BY_STATUS, {});
    data.pageLength.value = 50;
    await nextTick();
    expect(sent("groups").at(-1)!.limit).toBe(50);
  });

  it("fetches the totals over every record only when totals are on", async () => {
    useGroupByData("Sales Order", BY_STATUS, {});
    expect(sent("totals")).toEqual([]);

    h.answers.totals = [{ _aggregate_0: 690 }];
    const data = useGroupByData(
      "Sales Order",
      { ...BY_STATUS, showTotals: true },
      { docstatus: 1 }
    );
    expect(sent("totals")).toEqual([
      { filters: { docstatus: 1 }, fields: [{ COUNT: "name", as: "_aggregate_0" }], limit: 1 },
    ]);
    await settle();
    expect(data.totals.value).toEqual({ _aggregate_0: 690 });
  });

  it("drops the totals once the last aggregate is removed", async () => {
    h.answers.totals = [{ _aggregate_0: 690 }];
    const groupBy = ref<GroupBySettings>({ ...BY_STATUS, showTotals: true });
    const data = useGroupByData("Sales Order", groupBy, {});
    await settle();
    expect(data.totals.value).toEqual({ _aggregate_0: 690 });

    groupBy.value = { ...groupBy.value, aggregates: [] };
    await nextTick();
    expect(data.totals.value).toBeNull();
  });

  it("keeps the loaded pages when only a column width changes", async () => {
    const groupBy = ref<GroupBySettings>({ ...BY_STATUS });
    const data = useGroupByData("Sales Order", groupBy, {});
    data.loadMore();
    const calls = sent("groups").length;

    groupBy.value = { ...groupBy.value, widths: { status: "300px" } };
    await nextTick();
    expect(sent("groups").length).toBe(calls);

    groupBy.value = {
      ...groupBy.value,
      sort: [{ fieldname: "status", direction: "asc" }],
    };
    await nextTick();
    expect(sent("groups").at(-1)).toMatchObject({ order_by: "status asc", limit: 20 });
  });

  it("counts up to the cap, then keeps paging while pages come back full", async () => {
    h.answers.keys = Array.from({ length: 1000 }, (_, status) => ({ status }));
    h.answers.groups = [{ status: 1 }, { status: 2 }];
    const data = useGroupByData("Sales Order", BY_STATUS, {});
    data.pageLength.value = 2;
    await nextTick();
    expect(sent("keys").at(-1)!.limit).toBe(1000);
    expect(sent("groups").at(-1)!.limit).toBe(2);

    await settle();
    expect(data.totalCapped.value).toBe(true);
    expect(data.hasNextPage.value).toBe(true);

    h.answers.groups = [{ status: 1 }, { status: 2 }, { status: 3 }];
    data.loadMore();
    await settle();
    expect(data.hasNextPage.value).toBe(false);
  });

  it("offers more groups only while some are not loaded, under the cap", async () => {
    h.answers.keys = [{ status: "Won" }, { status: "Lost" }];
    h.answers.groups = [{ status: "Won" }];
    const data = useGroupByData("Sales Order", BY_STATUS, {});
    await settle();
    expect(data.hasNextPage.value).toBe(true);

    h.answers.groups = [{ status: "Won" }, { status: "Lost" }];
    data.loadMore();
    await settle();
    expect(data.hasNextPage.value).toBe(false);
  });
});
