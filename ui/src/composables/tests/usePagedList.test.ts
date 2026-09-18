// The pager on its own: which page asks for the count, what Load More refuses, and how a
// reload during a Load More drops the late page.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { usePagedList } from "../usePagedList";

const api = vi.hoisted(() => ({ listDocuments: vi.fn() }));

vi.mock("../../api", () => ({ listDocuments: api.listDocuments }));

type Answer = {
  data: { name: string }[];
  has_next_page: boolean;
  count?: number | null;
  count_capped?: boolean;
};

function deferred() {
  let resolve!: (value: Answer) => void;
  const promise = new Promise<Answer>((res) => (resolve = res));
  return { promise, resolve };
}

function rowsNamed(...names: string[]) {
  return names.map((name) => ({ name }));
}

function includes() {
  return api.listDocuments.mock.calls.map(([, , options]) => options?.include);
}

beforeEach(() => {
  api.listDocuments.mockReset();
});

describe("usePagedList", () => {
  it("asks only the first page for the count", async () => {
    api.listDocuments
      .mockResolvedValueOnce({ data: rowsNamed("a", "b"), has_next_page: true, count: 5 })
      .mockResolvedValueOnce({ data: rowsNamed("c"), has_next_page: false });
    const list = usePagedList("ToDo", { fields: ["name"] }, { pageLength: 2, withCount: true });
    await list.reload();
    await list.loadMore();
    expect(includes()).toEqual([["count"], undefined]);
    expect(api.listDocuments.mock.calls[1][1]).toMatchObject({ start: 2, limit: 2 });
    expect(list.rows.value.map((row) => row.name)).toEqual(["a", "b", "c"]);
    expect(list.count.value).toBe(5);
    expect(list.hasNextPage.value).toBe(false);
  });

  it("sends no include without withCount", async () => {
    api.listDocuments.mockResolvedValueOnce({ data: [], has_next_page: false });
    const list = usePagedList("ToDo", {});
    await list.reload();
    expect(includes()).toEqual([undefined]);
    expect(list.count.value).toBeNull();
  });

  it("refuses a Load More while a page is in flight", async () => {
    const first = deferred();
    api.listDocuments.mockReturnValueOnce(first.promise);
    const list = usePagedList("ToDo", {}, { pageLength: 1 });
    const loading = list.reload();
    await list.loadMore();
    expect(api.listDocuments).toHaveBeenCalledTimes(1);
    first.resolve({ data: rowsNamed("a"), has_next_page: true });
    await loading;
    api.listDocuments.mockResolvedValueOnce({ data: rowsNamed("b"), has_next_page: false });
    await list.loadMore();
    expect(api.listDocuments).toHaveBeenCalledTimes(2);
    expect(list.rows.value.map((row) => row.name)).toEqual(["a", "b"]);
  });

  it("drops a Load More page that lands after a reload", async () => {
    api.listDocuments.mockResolvedValueOnce({ data: rowsNamed("a"), has_next_page: true });
    const list = usePagedList("ToDo", {}, { pageLength: 1 });
    await list.reload();

    const late = deferred();
    const fresh = deferred();
    api.listDocuments.mockReturnValueOnce(late.promise).mockReturnValueOnce(fresh.promise);
    const more = list.loadMore();
    const again = list.reload();
    fresh.resolve({ data: rowsNamed("x"), has_next_page: false });
    await again;
    late.resolve({ data: rowsNamed("b"), has_next_page: false });
    await more;
    expect(list.rows.value.map((row) => row.name)).toEqual(["x"]);
    expect(list.loading.value).toBe(false);
  });

  it("exposes a null and a capped count", async () => {
    api.listDocuments.mockResolvedValueOnce({ data: rowsNamed("a"), has_next_page: true, count: null });
    const list = usePagedList("ToDo", {}, { withCount: true });
    await list.reload();
    expect(list.count.value).toBeNull();
    expect(list.countCapped.value).toBe(false);

    api.listDocuments.mockResolvedValueOnce({
      data: rowsNamed("a"),
      has_next_page: true,
      count: 1000,
      count_capped: true,
    });
    await list.reload();
    expect(list.count.value).toBe(1000);
    expect(list.countCapped.value).toBe(true);
  });

  it("keeps the error of the latest request only", async () => {
    api.listDocuments.mockRejectedValueOnce(new Error("Not permitted"));
    const list = usePagedList("ToDo", {});
    await list.reload();
    expect((list.error.value as Error).message).toBe("Not permitted");
    api.listDocuments.mockResolvedValueOnce({ data: [], has_next_page: false });
    await list.reload();
    expect(list.error.value).toBeNull();
  });
});
