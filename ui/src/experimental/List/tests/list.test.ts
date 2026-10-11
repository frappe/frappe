import { afterEach, describe, expect, it } from "vitest";
import { reactive } from "vue";
import { List } from "../index";
import type { ListRowData } from "../types";
import { flush, mount, unmountAll } from "./mount";

const columns = [
  { fieldname: "name", label: "Name" },
  { fieldname: "status", label: "Status" },
  { fieldname: "amount", label: "Amount", align: "right" as const },
];
const rows = [
  { name: "A", status: "Open", amount: 10 },
  { name: "B", status: { label: "Closed" }, amount: 20 },
];
const rowLink = (row: ListRowData) => `/lead/${row.name}`;

afterEach(unmountAll);

/** A router navigation lands a macrotask later than a render. */
async function settle() {
  await new Promise((resolve) => setTimeout(resolve));
  await flush();
}

function rowsOf(root: HTMLElement) {
  return root.querySelectorAll<HTMLElement>("[data-slot='list-row']");
}

function headerButtons(root: HTMLElement) {
  return root.querySelectorAll<HTMLButtonElement>(
    "[data-slot='list-header-cell'] button"
  );
}

describe("List rows", () => {
  it("renders every row as a link to rowLink's route", async () => {
    const { root } = await mount(List, { columns, rows, rowLink });
    const links = rowsOf(root);
    expect(links).toHaveLength(2);
    expect(links[0].tagName).toBe("A");
    expect(links[0].getAttribute("href")).toBe("/lead/A");
  });

  it("mounts only a window of a long list", async () => {
    const many = Array.from({ length: 30 }, (_, index) => ({
      name: `R${index}`,
    }));
    const { root } = await mount(List, { columns, rows: many });
    await flush();
    const mounted = rowsOf(root).length;
    expect(mounted).toBeGreaterThan(0);
    expect(mounted).toBeLessThan(30);
  });

  it("renders a plain row without rowLink", async () => {
    const { root } = await mount(List, { columns, rows });
    expect(rowsOf(root)[0].tagName).toBe("DIV");
  });

  it("reads an object cell's label and right-aligns a right column", async () => {
    const { root } = await mount(List, { columns, rows });
    const cells = rowsOf(root)[1].querySelectorAll("[data-slot='list-cell']");
    expect(cells[2].textContent).toContain("Closed");
    expect(cells[3].className).toContain("justify-end");
  });

  it("renders the cell slot in place of the text", async () => {
    const { root } = await mount(
      List,
      { columns, rows },
      { cell: () => "custom" }
    );
    expect(rowsOf(root)[0].textContent).toContain("custom");
    expect(rowsOf(root)[0].textContent).not.toContain("Open");
  });
});

describe("List selection", () => {
  it("a checkbox click toggles the row and does not navigate", async () => {
    const state = reactive({ selection: [] as string[] });
    const { root, router } = await mount(List, {
      columns,
      rows,
      rowLink,
      get selection() {
        return state.selection;
      },
      "onUpdate:selection": (value: string[]) => (state.selection = value),
    });

    rowsOf(root)[0].querySelector<HTMLElement>("[role='checkbox']")!.click();
    await settle();

    expect(state.selection).toEqual(["A"]);
    expect(router.currentRoute.value.path).toBe("/");
    expect(
      rowsOf(root)[0]
        .querySelector("[role='checkbox']")
        ?.getAttribute("aria-checked")
    ).toBe("true");
  });

  it("a click on the row itself does navigate", async () => {
    const { root, router } = await mount(List, { columns, rows, rowLink });

    rowsOf(root)[1].click();
    await settle();

    expect(router.currentRoute.value.path).toBe("/lead/B");
  });

  it("the header checkbox selects every shown row", async () => {
    const state = reactive({ selection: [] as string[] });
    const { root } = await mount(List, {
      columns,
      rows,
      get selection() {
        return state.selection;
      },
      "onUpdate:selection": (value: string[]) => (state.selection = value),
    });

    root
      .querySelector<HTMLInputElement>(
        "[data-slot='list-header'] input[type='checkbox']"
      )!
      .click();
    await flush();

    expect(state.selection).toEqual(["A", "B"]);
  });
});

describe("List sort", () => {
  it("draws plain headers when no sort model is bound", async () => {
    const { root } = await mount(List, { columns, rows });
    expect(headerButtons(root)).toHaveLength(0);
  });

  it("a header click makes that column the sort, and the next click flips it", async () => {
    const state = reactive({
      sort: [] as { fieldname: string; direction: string }[],
    });
    const { root } = await mount(List, {
      columns,
      rows,
      get sort() {
        return state.sort;
      },
      "onUpdate:sort": (value: typeof state.sort) => (state.sort = value),
    });

    headerButtons(root)[1].click();
    await flush();
    expect(state.sort).toEqual([{ fieldname: "status", direction: "asc" }]);

    headerButtons(root)[1].click();
    await flush();
    expect(state.sort).toEqual([{ fieldname: "status", direction: "desc" }]);
    expect(
      headerButtons(root)[1]
        .closest("[data-slot='list-header-cell']")
        ?.getAttribute("aria-sort")
    ).toBe("descending");
  });
});

describe("List states", () => {
  it("shows skeleton rows while loading with nothing to show", async () => {
    const { root } = await mount(List, { columns, rows: [], loading: true });
    expect(rowsOf(root)).toHaveLength(10);
    expect(root.textContent).not.toContain("No records");
  });

  it("shows the empty text, or the empty slot, once loaded with no rows", async () => {
    const plain = await mount(List, { columns, rows: [] });
    expect(plain.root.textContent).toContain("No records");
    unmountAll();

    const slotted = await mount(
      List,
      { columns, rows: [] },
      { empty: () => "Nothing here" }
    );
    expect(slotted.root.textContent).toContain("Nothing here");
    expect(slotted.root.textContent).not.toContain("No records");
  });
});

describe("List column resize", () => {
  it("a double click on the resizer emits column-reset", async () => {
    const resets: { fieldname: string }[] = [];
    const { root } = await mount(List, {
      columns,
      rows,
      "onColumn-reset": (payload: { fieldname: string }) =>
        resets.push(payload),
    });

    root
      .querySelector<HTMLElement>(".cursor-col-resize")!
      .dispatchEvent(new MouseEvent("dblclick", { bubbles: true }));

    expect(resets).toEqual([{ fieldname: "name" }]);
  });

  it("a drag shows the draft width and emits column-resize on release", async () => {
    const resizes: { fieldname: string; width: string }[] = [];
    const { root } = await mount(List, {
      columns,
      rows,
      "onColumn-resize": (payload: { fieldname: string; width: string }) =>
        resizes.push(payload),
    });
    const handle = root.querySelector<HTMLElement>(".cursor-col-resize")!;
    const list = root.querySelector<HTMLElement>("[data-slot='list']")!;
    handle.parentElement!.getBoundingClientRect = () =>
      ({ width: 120 } as DOMRect);

    handle.dispatchEvent(
      new MouseEvent("pointerdown", { bubbles: true, clientX: 100 })
    );
    window.dispatchEvent(new MouseEvent("pointermove", { clientX: 180 }));
    await flush();
    expect(list.getAttribute("style")).toContain("200px");

    window.dispatchEvent(new MouseEvent("pointerup"));
    await flush();
    expect(resizes).toEqual([{ fieldname: "name", width: "200px" }]);
    expect(list.getAttribute("style")).not.toContain("200px");
  });

  it("a cancelled drag drops the draft and emits nothing", async () => {
    const resizes: unknown[] = [];
    const { root } = await mount(List, {
      columns,
      rows,
      "onColumn-resize": (payload: unknown) => resizes.push(payload),
    });
    const handle = root.querySelector<HTMLElement>(".cursor-col-resize")!;
    const list = root.querySelector<HTMLElement>("[data-slot='list']")!;
    handle.parentElement!.getBoundingClientRect = () =>
      ({ width: 120 } as DOMRect);

    handle.dispatchEvent(
      new MouseEvent("pointerdown", { bubbles: true, clientX: 100 })
    );
    window.dispatchEvent(new MouseEvent("pointermove", { clientX: 180 }));
    await flush();
    expect(list.getAttribute("style")).toContain("200px");

    window.dispatchEvent(new Event("pointercancel"));
    await flush();
    expect(list.getAttribute("style")).not.toContain("200px");
    window.dispatchEvent(new MouseEvent("pointermove", { clientX: 260 }));
    await flush();
    expect(list.getAttribute("style")).not.toContain("260px");
    expect(resizes).toEqual([]);
  });
});
