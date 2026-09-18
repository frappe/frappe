// The fetching companion on its own: the count beside the first page, the capped and
// unknown states the footer draws, and the exact count asked for on click.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick, ref } from "vue";
import { useListData } from "../useListData";
import type { UseListView } from "../useListView";

const api = vi.hoisted(() => ({ listDocuments: vi.fn(), countDocuments: vi.fn() }));

vi.mock("../../../api", () => ({
  listDocuments: api.listDocuments,
  countDocuments: api.countDocuments,
}));

type Answer = {
  data: { name: string }[];
  has_next_page: boolean;
  count?: number | null;
  count_capped?: boolean;
};

function fakeView() {
  const view = {
    columns: { wire: ref([{ key: "name" }]), synthetic: ref([]) },
    filters: { wire: ref<Record<string, unknown>>({ status: "Open" }) },
    sort: { orderBy: ref("modified desc") },
  };
  return { view, typed: view as unknown as UseListView };
}

async function settle() {
  await Promise.resolve();
  await Promise.resolve();
  await nextTick();
}

function answer(page: Answer) {
  api.listDocuments.mockResolvedValueOnce(page);
}

beforeEach(() => {
  api.listDocuments.mockReset().mockResolvedValue({ data: [], has_next_page: false });
  api.countDocuments.mockReset().mockResolvedValue({ data: 4321 });
});

describe("useListData", () => {
  it("reads the count beside the first page and shows it as the total", async () => {
    answer({ data: [{ name: "T-1" }], has_next_page: true, count: 50, count_capped: false });
    const data = useListData("ToDo", fakeView().typed);
    await settle();
    expect(api.listDocuments).toHaveBeenCalledWith(
      "ToDo",
      expect.objectContaining({ filters: { status: "Open" }, start: 0 }),
      { include: ["count"] }
    );
    expect(data.totalCount.value).toBe(50);
    expect(data.totalCapped.value).toBe(false);
    expect(data.totalUnknown.value).toBe(false);
  });

  it("reads a capped count as a floor and lifts it with the exact count on request", async () => {
    answer({ data: [{ name: "T-1" }], has_next_page: true, count: 1000, count_capped: true });
    const data = useListData("ToDo", fakeView().typed);
    await settle();
    expect(data.totalCount.value).toBe(1000);
    expect(data.totalCapped.value).toBe(true);

    await data.countExact();
    expect(api.countDocuments).toHaveBeenCalledWith("ToDo", { filters: { status: "Open" } });
    expect(data.totalCount.value).toBe(4321);
    expect(data.totalCapped.value).toBe(false);
  });

  it("keeps the capped count when the exact one is null or fails", async () => {
    answer({ data: [{ name: "T-1" }], has_next_page: true, count: 1000, count_capped: true });
    const data = useListData("ToDo", fakeView().typed);
    await settle();

    api.countDocuments.mockResolvedValueOnce({ data: null });
    await data.countExact();
    expect(data.totalCount.value).toBe(1000);
    expect(data.totalCapped.value).toBe(true);

    api.countDocuments.mockRejectedValueOnce(new Error("timeout"));
    await data.countExact();
    expect(data.totalCount.value).toBe(1000);
    expect(data.totalCapped.value).toBe(true);
  });

  it("drops an exact count that lands after the filters changed", async () => {
    answer({ data: [{ name: "T-1" }], has_next_page: true, count: 1000, count_capped: true });
    const { view, typed } = fakeView();
    const data = useListData("ToDo", typed);
    await settle();

    let resolve!: (value: { data: number }) => void;
    api.countDocuments.mockReturnValueOnce(new Promise((res) => (resolve = res)));
    const asked = data.countExact();
    answer({ data: [], has_next_page: false, count: 0, count_capped: false });
    view.filters.wire.value = { status: "Closed" };
    await settle();
    resolve({ data: 4321 });
    await asked;
    expect(data.totalCount.value).toBe(0);
    expect(data.totalCapped.value).toBe(false);
  });

  it("reads the rows as the total when the server gave up counting", async () => {
    answer({ data: [{ name: "T-1" }, { name: "T-2" }], has_next_page: true, count: null });
    const data = useListData("ToDo", fakeView().typed);
    expect(data.totalUnknown.value).toBe(false);
    await settle();
    expect(data.totalUnknown.value).toBe(true);
    expect(data.totalCount.value).toBe(2);
    expect(data.totalCapped.value).toBe(false);
  });

  it("does not read a failed first page as unknown", async () => {
    api.listDocuments.mockRejectedValueOnce(new Error("Not permitted"));
    const data = useListData("ToDo", fakeView().typed);
    await settle();
    expect(data.totalUnknown.value).toBe(false);
    expect(data.totalCount.value).toBe(0);
  });
});
