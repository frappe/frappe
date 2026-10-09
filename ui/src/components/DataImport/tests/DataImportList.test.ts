import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick } from "vue";
import type { App, VNode } from "vue";
import { setConfig } from "frappe-ui";
import DataImportList from "../DataImportList.vue";
import { useDataImportList } from "../useDataImportList";
import type { UseDataImportList } from "../useDataImportList";

interface ListParams {
  doctype: string;
  fields: string[];
  filters: unknown[];
  order_by: string;
  start: number;
  limit: number;
}

let app: App | undefined;
let host: HTMLElement | undefined;
let fetcher: ReturnType<typeof vi.fn>;
let pages: Record<string, unknown>[][];

function row(n: number) {
  return {
    name: `ToDo Import-${n}`,
    reference_doctype: "ToDo",
    import_type: "Insert New Records",
    status: n === 1 ? "In Progress" : "Success",
    creation: "2026-10-01 10:00:00",
  };
}

beforeEach(() => {
  pages = [[row(1), row(2)]];
  fetcher = vi.fn(async ({ params }: { params: ListParams }) => {
    return pages[params.start / params.limit] ?? [];
  });
  setConfig("resourceFetcher", fetcher);
});

afterEach(() => {
  app?.unmount();
  host?.remove();
  document.body.innerHTML = "";
  app = undefined;
  host = undefined;
  setConfig("resourceFetcher", undefined as never);
});

async function flush() {
  for (let i = 0; i < 5; i++) {
    await Promise.resolve();
    await nextTick();
  }
}

function lastParams(): ListParams {
  return fetcher.mock.calls.at(-1)![0].params;
}

async function mount(
  options: Parameters<typeof useDataImportList>[0] = {},
  listeners: { onOpen?: (name: string) => void; onNew?: () => void } = {}
) {
  let list!: UseDataImportList;
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp(
    defineComponent({
      setup() {
        list = useDataImportList(options);
        return () => h(DataImportList, { list, ...listeners });
      },
    })
  );
  app.mount(host);
  await flush();
  return list;
}

// frappe-ui's select opens in a popover, so its options are read off the vnode.
function findVNode(
  vnode: VNode,
  match: (vnode: VNode) => boolean
): VNode | undefined {
  if (match(vnode)) return vnode;
  const children = [
    ...(Array.isArray(vnode.children) ? (vnode.children as VNode[]) : []),
    ...(vnode.component ? [vnode.component.subTree] : []),
  ];
  for (const child of children) {
    const found = child && typeof child === "object" && findVNode(child, match);
    if (found) return found;
  }
}

function buttonWithText(text: string) {
  return [...host!.querySelectorAll("button")].find((b) =>
    b.textContent?.includes(text)
  );
}

describe("useDataImportList", () => {
  it("fetches Data Imports with the old fields and order", async () => {
    await mount();
    const params = lastParams();
    expect(params.doctype).toBe("Data Import");
    expect(params.order_by).toBe("modified desc");
    expect(params.fields).toEqual([
      "name",
      "reference_doctype",
      "import_type",
      "status",
      "creation",
      "mute_emails",
      "import_file",
      "google_sheets_url",
      "template_options",
    ]);
    expect(params.filters).toEqual([]);
  });

  it("limits the list to the given doctype", async () => {
    const list = await mount({ doctype: "CRM Lead" });
    expect(lastParams().filters).toEqual([
      ["reference_doctype", "=", "CRM Lead"],
    ]);

    list.status.value = "Error";
    await flush();
    expect(lastParams().filters).toEqual([
      ["reference_doctype", "=", "CRM Lead"],
      ["status", "=", "Error"],
    ]);
  });

  it("starts on the given status, in the first fetch", async () => {
    const list = await mount({ doctype: "CRM Lead", status: "Pending" });
    expect(list.status.value).toBe("Pending");
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(lastParams().filters).toEqual([
      ["reference_doctype", "=", "CRM Lead"],
      ["status", "=", "Pending"],
    ]);
  });

  it("refetches from the first page when search or status changes", async () => {
    pages = [Array.from({ length: 20 }, (_, i) => row(i + 1)), [row(21)]];
    const list = await mount();
    list.loadMore();
    await flush();
    expect(lastParams().start).toBe(20);

    list.search.value = "ToDo";
    await flush();
    expect(lastParams().start).toBe(0);
    expect(lastParams().filters).toEqual([["name", "like", "%ToDo%"]]);

    list.status.value = "In Progress";
    await flush();
    expect(lastParams().filters).toEqual([
      ["name", "like", "%ToDo%"],
      ["status", "=", "In Progress"],
    ]);

    list.status.value = "All";
    list.search.value = "";
    await flush();
    expect(lastParams().filters).toEqual([]);
  });
});

describe("DataImportList", () => {
  it("renders a row per import with its status", async () => {
    await mount();
    expect(host!.textContent).toContain("ToDo");
    expect(host!.textContent).toContain("In Progress");
    expect(host!.textContent).toContain("Insert");
  });

  it("offers every status in the filter", async () => {
    await mount();
    const select = findVNode(
      app!._instance!.subTree,
      (vnode) => vnode.props?.type === "select"
    );
    const options = select!.props!.options.map(
      (o: { value: string }) => o.value
    );
    expect(options).toEqual([
      "All",
      "Pending",
      "In Progress",
      "Success",
      "Partial Success",
      "Error",
      "Timed Out",
    ]);
  });

  it("searches as the user types", async () => {
    await mount();
    const input = host!.querySelector("input[type=text]") as HTMLInputElement;
    input.value = "Lead";
    input.dispatchEvent(new Event("input"));
    await flush();
    expect(lastParams().filters).toEqual([["name", "like", "%Lead%"]]);
  });

  it("loads the next page and appends it", async () => {
    pages = [Array.from({ length: 20 }, (_, i) => row(i + 1)), [row(21)]];
    const list = await mount();
    buttonWithText("Load More")!.click();
    await flush();
    expect(lastParams().start).toBe(20);
    expect(list.rows.value).toHaveLength(21);
    expect(buttonWithText("Load More")).toBeUndefined();
  });

  it("hides Load More when the first page is short", async () => {
    await mount();
    expect(buttonWithText("Load More")).toBeUndefined();
  });

  it("emits open with the name when a row is clicked", async () => {
    const onOpen = vi.fn();
    await mount({}, { onOpen });
    const rowEl = [
      ...host!.querySelectorAll(".cursor-pointer"),
    ][1] as HTMLElement;
    rowEl.click();
    expect(onOpen).toHaveBeenCalledWith("ToDo Import-2");
  });

  it("emits new from the Import button", async () => {
    const onNew = vi.fn();
    await mount({}, { onNew });
    buttonWithText("Import")!.click();
    expect(onNew).toHaveBeenCalledTimes(1);
  });

  it("shows the empty message when nothing matches", async () => {
    pages = [[]];
    await mount();
    expect(host!.textContent).toContain("No data imports found.");
  });
});
