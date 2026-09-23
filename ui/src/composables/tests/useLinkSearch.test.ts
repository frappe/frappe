// The link picker's search on its own: the last answer wins, and `data` tells "not asked
// yet" from "nothing found".
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import { useLinkSearch } from "../useLinkSearch";

const api = vi.hoisted(() => ({ searchDocuments: vi.fn() }));

vi.mock("../../api", () => ({ searchDocuments: api.searchDocuments }));

type Row = { value: string; label?: string; description?: string };

function deferred() {
  let resolve!: (value: { data: Row[] }) => void;
  const promise = new Promise<{ data: Row[] }>((res) => (resolve = res));
  return { promise, resolve };
}

beforeEach(() => {
  api.searchDocuments.mockReset();
});

describe("useLinkSearch", () => {
  it("is null until the first answer, then holds the shaped rows", async () => {
    api.searchDocuments.mockResolvedValueOnce({
      data: [
        { value: "T-1", label: "One", description: "first" },
        { value: "T-2", label: "" },
      ],
    });
    const search = useLinkSearch("ToDo", { status: "Open" }, 5);
    expect(search.data.value).toBeNull();
    await search.search("o");
    expect(api.searchDocuments).toHaveBeenCalledWith("ToDo", {
      txt: "o",
      filters: { status: "Open" },
      limit: 5,
    });
    expect(search.data.value).toEqual([
      { value: "T-1", label: "One", description: "first" },
      { value: "T-2", label: "T-2", description: undefined },
    ]);
    expect(search.loading.value).toBe(false);
  });

  it("leaves the record's name out of a titled option's description", async () => {
    api.searchDocuments.mockResolvedValueOnce({
      data: [{ value: "62e34b24e4", label: "tabPartner", description: "62e34b24e4, frappe.io" }],
    });
    const search = useLinkSearch("Contact");
    await search.search("");
    expect(search.data.value).toEqual([
      { value: "62e34b24e4", label: "tabPartner", description: "frappe.io" },
    ]);
  });

  it("lets the last answer win over an earlier one that lands late", async () => {
    const first = deferred();
    const second = deferred();
    api.searchDocuments.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
    const search = useLinkSearch("ToDo");
    const one = search.search("a");
    const two = search.search("ab");
    second.resolve({ data: [{ value: "ab" }] });
    await two;
    expect(search.loading.value).toBe(false);
    first.resolve({ data: [{ value: "a" }] });
    await one;
    expect(search.data.value?.map((row) => row.value)).toEqual(["ab"]);
  });

  it("does nothing without a doctype and reads the doctype live", async () => {
    api.searchDocuments.mockResolvedValue({ data: [] });
    const doctype = ref<string | undefined>(undefined);
    const search = useLinkSearch(doctype);
    await search.search("x");
    expect(api.searchDocuments).not.toHaveBeenCalled();
    doctype.value = "Contact";
    await search.search("x");
    expect(api.searchDocuments).toHaveBeenCalledWith("Contact", expect.objectContaining({ txt: "x" }));
  });

  it("keeps the failure and the last good answer", async () => {
    api.searchDocuments
      .mockResolvedValueOnce({ data: [{ value: "ok" }] })
      .mockRejectedValueOnce(new Error("Not permitted"));
    const search = useLinkSearch("ToDo");
    await search.search("");
    await search.search("bad");
    expect((search.error.value as Error).message).toBe("Not permitted");
    expect(search.data.value?.map((row) => row.value)).toEqual(["ok"]);
  });
});
