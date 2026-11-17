// The List renderer's acts for its columns, page size and Load More.
import { describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import { ActInvalid } from "@/acts/dispatcher";
import { listViewEntries } from "../listViewActs";
import { loadMore, setColumns, setPageSize } from "../listViewRuns";

const FIELDS = [
  { fieldname: "subject", label: "Subject", fieldtype: "Data" },
  { fieldname: "status", label: "Status", fieldtype: "Select", options: "Open\nClosed" },
  { fieldname: "secret", label: "Secret", fieldtype: "Data" },
  { fieldname: "section", label: "Section", fieldtype: "Section Break" },
];

function listView(options: { hasNext?: boolean } = {}) {
  const columns = ref<any[]>([
    { fieldname: "subject", label: "Subject", width: "200px" },
    { fieldname: "status", label: "Status" },
  ]);
  const view = {
    meta: ref({ fields: FIELDS, title_field: "subject" }),
    readable: (fieldname: string) => fieldname !== "secret",
    columns,
    resetColumns: vi.fn(async () => {}),
    pageSize: ref(20),
    show: vi.fn(),
    next: vi.fn(),
    settled: vi.fn(async () => {}),
    hasNextPage: ref(options.hasNext ?? true),
    totalCount: ref(150),
    rows: ref([{ name: "T-1", subject: "Fix it" }, { name: "T-2" }]),
  };
  return { ...view, view: view as any };
}

describe("list.set_columns", () => {
  it("writes the columns as the dialog does, keeping a kept column's width", async () => {
    const { view, columns } = listView();
    const written = await setColumns(view, { columns: [{ fieldname: "status" }, { fieldname: "subject" }] });
    expect(columns.value.map((column) => [column.fieldname, column.width])).toEqual([
      ["status", undefined],
      ["subject", "200px"],
    ]);
    expect(written.columns.map((column) => column.fieldname)).toEqual(["status", "subject"]);
    expect(view.settled).toHaveBeenCalled();
  });

  it("shows the field's own label, whatever label the caller sends", async () => {
    const { view } = listView();
    const written = await setColumns(view, { columns: [{ fieldname: "status", label: "Mine" }] } as any);
    expect(written.columns).toEqual([{ fieldname: "status", label: "Status" }]);
  });

  it("restores the default columns for an empty list", async () => {
    const { view, resetColumns } = listView();
    await setColumns(view, { columns: [] });
    expect(resetColumns).toHaveBeenCalledOnce();
  });

  it("refuses a field the reader may not see, a layout field, a name twice and an unknown name", async () => {
    const { view, columns } = listView();
    for (const names of [["secret"], ["section"], ["status", "status"], ["nope"]]) {
      await expect(setColumns(view, { columns: names.map((fieldname) => ({ fieldname })) })).rejects.toBeInstanceOf(ActInvalid);
    }
    expect(columns.value.map((column) => column.fieldname)).toEqual(["subject", "status"]);
  });
});

describe("list.set_page_size", () => {
  it("sets the size, waits for the rows and returns them", async () => {
    const { view, pageSize, show, settled } = listView();
    const answer = await setPageSize(view, { size: 100 });
    expect(pageSize.value).toBe(100);
    expect(show).toHaveBeenCalledWith(100);
    expect(settled).toHaveBeenCalled();
    expect(answer).toEqual({
      total: 150,
      rows: [
        { name: "T-1", title: "Fix it" },
        { name: "T-2", title: "T-2" },
      ],
    });
  });
});

describe("list.load_more", () => {
  it("asks for the next page and returns the rows", async () => {
    const { view, next } = listView();
    const answer = await loadMore(view);
    expect(next).toHaveBeenCalledOnce();
    expect(answer.total).toBe(150);
  });

  it("waits for a page already on its way before it asks for the next", async () => {
    const { view, next, settled } = listView();
    await loadMore(view);
    expect(settled.mock.invocationCallOrder[0]).toBeLessThan(next.mock.invocationCallOrder[0]);
  });

  it("refuses when no next page is left", async () => {
    const { view, next } = listView({ hasNext: false });
    await expect(loadMore(view)).rejects.toBeInstanceOf(ActInvalid);
    expect(next).not.toHaveBeenCalled();
  });
});

describe("list view act entries", () => {
  it("hides Load More, like its button, when no next page is left", () => {
    const hidden = (hasNext: boolean) =>
      listViewEntries({ hasNextPage: ref(hasNext) } as any).filter((entry) => entry.hidden).map((entry) => entry.item.name);
    expect(hidden(true)).toEqual([]);
    expect(hidden(false)).toEqual(["load_more"]);
  });
});
