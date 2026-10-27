import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, ref } from "vue";
import type { App } from "vue";

vi.mock("frappe-ui", async (importOriginal) => ({
  ...(await importOriginal<typeof import("frappe-ui")>()),
  ...(await import("./menuStubs")),
}));

import Grid from "../Grid.vue";
import { ROW_ID } from "../../Fields/rowIdentity";

let app: App | undefined;
let host: HTMLElement | undefined;

afterEach(() => {
  app?.unmount();
  host?.remove();
  app = undefined;
  host = undefined;
});

const COLUMNS = [{ fieldname: "a" }, { fieldname: "b" }, { fieldname: "c" }];

function render(
  initial: Record<string, any>[],
  props: Record<string, any> = {}
) {
  const rows = ref(initial);
  const events: { commit: string[]; add: number; change: number } = {
    commit: [],
    add: 0,
    change: 0,
  };
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({
    render: () =>
      h(
        Grid,
        {
          columns: COLUMNS,
          modelValue: rows.value,
          "onUpdate:modelValue": (next: any) => (rows.value = next),
          newRow: () => ({ c: "default" }),
          onCommit: ({ row, column }: any) =>
            events.commit.push(`${rows.value.indexOf(row)}.${column.fieldname}`),
          onAdd: () => events.add++,
          onChange: () => events.change++,
          ...props,
        },
        {
          cell: ({ row, column, update }: any) =>
            h("input", {
              value: row[column.fieldname] ?? "",
              onInput: (e: Event) => update((e.target as HTMLInputElement).value),
            }),
        }
      ),
  });
  app.mount(host);
  return { rows, events };
}

function input(row: number, column: number): HTMLInputElement {
  const rowEl = host!.querySelectorAll(".grid-row")[row];
  return rowEl.querySelectorAll<HTMLInputElement>(".grid-cell input")[column];
}

function press(el: HTMLElement, key: string, mods: KeyboardEventInit = {}) {
  el.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true, ...mods }));
}

function paste(el: HTMLElement, text: string): Event {
  const event = new Event("paste", { bubbles: true, cancelable: true });
  Object.defineProperty(event, "clipboardData", { value: { getData: () => text } });
  el.dispatchEvent(event);
  return event;
}

function menuItem(row: number, label: string): HTMLElement | undefined {
  const rowEl = host!.querySelectorAll(".grid-row")[row];
  return rowEl?.querySelector<HTMLElement>(`[data-menu-item="${label}"]`) ?? undefined;
}

function menuLabels(row: number): string[] {
  const rowEl = host!.querySelectorAll(".grid-row")[row];
  return [...rowEl.querySelectorAll("[data-menu-item]")].map((el) => el.textContent!);
}

function rightClick(el: Element) {
  el.dispatchEvent(new MouseEvent("contextmenu", { bubbles: true, cancelable: true }));
}

function contextItem(label: string): HTMLElement | null {
  return host!.querySelector(`[data-context-menu] [data-menu-item="${label}"]`);
}

const twoRows = () => [
  { name: "r1", a: "1", b: "2", c: "3" },
  { name: "r2", a: "4", b: "5", c: "6" },
];

describe("Grid arrow keys", () => {
  it("moves Up and Down to the same column, and stops at the grid's edges", () => {
    render(twoRows());
    input(0, 1).focus();
    press(input(0, 1), "ArrowDown");
    expect(document.activeElement).toBe(input(1, 1));
    press(input(1, 1), "ArrowDown");
    expect(document.activeElement).toBe(input(1, 1));
    press(input(1, 1), "ArrowUp");
    expect(document.activeElement).toBe(input(0, 1));
    press(input(0, 1), "ArrowUp");
    expect(document.activeElement).toBe(input(0, 1));
  });

  it("moves Left and Right only from the start or end of the text", () => {
    render([{ name: "r1", a: "ab", b: "cd", c: "ef" }]);
    const b = input(0, 1);
    b.focus();
    b.setSelectionRange(1, 1);
    press(b, "ArrowRight");
    expect(document.activeElement).toBe(b);
    b.setSelectionRange(2, 2);
    press(b, "ArrowRight");
    expect(document.activeElement).toBe(input(0, 2));
    press(input(0, 2), "ArrowRight");
    expect(document.activeElement).toBe(input(0, 2));

    b.focus();
    b.setSelectionRange(0, 0);
    press(b, "ArrowLeft");
    expect(document.activeElement).toBe(input(0, 0));
    press(input(0, 0), "ArrowLeft");
    expect(document.activeElement).toBe(input(0, 0));
  });

  it("leaves the keys to a picker whose open trigger sits beside the input", () => {
    render(twoRows());
    const a = input(0, 0);
    const trigger = document.createElement("button");
    trigger.setAttribute("aria-expanded", "true");
    a.parentElement!.appendChild(trigger);
    a.focus();
    press(a, "ArrowDown");
    expect(document.activeElement).toBe(a);
  });

  it("leaves the keys to an open picker", () => {
    render(twoRows());
    const a = input(0, 0);
    a.setAttribute("aria-expanded", "true");
    a.focus();
    press(a, "ArrowDown");
    expect(document.activeElement).toBe(a);
  });

  it("does nothing in a read-only grid", () => {
    render(twoRows(), { disabled: true });
    const a = input(0, 0);
    a.focus();
    press(a, "ArrowDown");
    expect(document.activeElement).toBe(a);
  });
});

describe("Grid paste", () => {
  it("fills a 2×3 block from the cell and adds the missing row, one commit per changed cell", async () => {
    const { rows, events } = render(twoRows());
    const event = paste(input(1, 0), "x\ty\tz\nu\tv\tw\n");
    await nextTick();
    expect(event.defaultPrevented).toBe(true);
    expect(rows.value.map(({ a, b, c }) => [a, b, c])).toEqual([
      ["1", "2", "3"],
      ["x", "y", "z"],
      ["u", "v", "w"],
    ]);
    expect(events.add).toBe(1);
    expect(events.commit).toEqual(["1.a", "1.b", "1.c", "2.a", "2.b", "2.c"]);
    expect(events.change).toBe(1);
  });

  it("starts at the pasted column and commits only the cells that changed", async () => {
    const { rows, events } = render(twoRows());
    paste(input(0, 1), "2\tnew\n5\t6");
    await nextTick();
    expect(rows.value.map(({ b, c }) => [b, c])).toEqual([
      ["2", "new"],
      ["5", "6"],
    ]);
    expect(events.commit).toEqual(["0.c"]);
  });

  it("parses each cell through parsePaste and skips the cells it refuses", async () => {
    const parsePaste = (_row: any, column: any, text: string) =>
      column.fieldname === "b" ? null : { value: Number(text) };
    const { rows } = render(twoRows(), { parsePaste });
    paste(input(0, 0), "7\t8\t9");
    await nextTick();
    expect(rows.value[0]).toMatchObject({ a: 7, b: "2", c: 9 });
  });

  it("blurs the cell before writing, so its control cannot commit a stale draft, then refocuses it", async () => {
    const { rows } = render(twoRows());
    const target = input(0, 0);
    target.focus();
    const seen: string[] = [];
    target.addEventListener("blur", () => seen.push(`blur:${rows.value[0].a}`));
    paste(target, "x\ty");
    await nextTick();
    expect(seen).toEqual(["blur:1"]);
    expect(document.activeElement).toBe(input(0, 0));
  });

  it("does nothing in a read-only grid", () => {
    const { events } = render(twoRows(), { disabled: true });
    const event = paste(input(0, 0), "x\ty");
    expect(event.defaultPrevented).toBe(false);
    expect(events.commit).toEqual([]);
  });

  it("writes every cell before a commit handler can replace the rows", async () => {
    const original = twoRows();
    const { rows } = render(original, {
      onCommit: () => (rows.value = []),
    });
    paste(input(0, 0), "x\ty\nu\tv");
    await nextTick();
    expect(original.map(({ a, b }) => [a, b])).toEqual([
      ["x", "y"],
      ["u", "v"],
    ]);
  });

  it("leaves a single value to the input's own paste", () => {
    const { events } = render(twoRows());
    const event = paste(input(0, 0), "just one\n");
    expect(event.defaultPrevented).toBe(false);
    expect(events.commit).toEqual([]);
  });
});

describe("Grid row menu", () => {
  it("holds Edit, Insert Above, Insert Below and Duplicate, with no separate Edit button", () => {
    render(twoRows());
    expect(menuLabels(0)).toEqual(["Edit", "Insert Above", "Insert Below", "Duplicate"]);
    const endCol = host!.querySelectorAll(".grid-row")[0].lastElementChild!;
    expect(endCol.querySelectorAll("button:not([data-menu-item])")).toHaveLength(1);
    expect(host!.querySelector('[aria-label="Edit Row"]')).toBeNull();
  });

  it("emits edit with the row and its index", () => {
    const onEdit = vi.fn();
    const initial = twoRows();
    render(initial, { onEdit });
    menuItem(1, "Edit")!.click();
    expect(onEdit).toHaveBeenCalledWith({ row: initial[1], index: 1 });
  });

  it("opens the same menu on a right-click, for the row under the pointer", async () => {
    const onEdit = vi.fn();
    const { rows } = render(twoRows(), { onEdit });
    rightClick(input(1, 2));
    await nextTick();
    const labels = [...host!.querySelectorAll("[data-context-menu] [data-menu-item]")];
    expect(labels.map((el) => el.textContent)).toEqual(menuLabels(1));
    contextItem("Duplicate")!.click();
    await nextTick();
    expect(rows.value.map((r) => r.name ?? `copy of ${r.a}`)).toEqual(["r1", "r2", "copy of 4"]);
    rightClick(input(0, 0));
    await nextTick();
    contextItem("Edit")!.click();
    expect(onEdit).toHaveBeenCalledWith(expect.objectContaining({ index: 0 }));
  });

  it("keeps the menu in a read-only grid, with Edit only", async () => {
    render(twoRows(), { disabled: true });
    expect(menuLabels(0)).toEqual(["Edit"]);
    rightClick(host!.querySelectorAll(".grid-row")[1]);
    await nextTick();
    expect(host!.querySelectorAll("[data-context-menu] [data-menu-item]")).toHaveLength(1);
  });
});

describe("Grid insert and duplicate", () => {
  it("inserts a row above and below from the row's menu, with the new-row defaults", async () => {
    const { rows } = render(twoRows());
    menuItem(1, "Insert Above")!.click();
    await nextTick();
    expect(rows.value.map((r) => r.name ?? r.c)).toEqual(["r1", "default", "r2"]);
    menuItem(0, "Insert Below")!.click();
    await nextTick();
    expect(rows.value.map((r) => r.name ?? r.c)).toEqual(["r1", "default", "default", "r2"]);
    expect(rows.value[1][ROW_ID]).toBeTruthy();
  });

  it("duplicates a row below its source, with no name and a fresh __row_id", async () => {
    const { rows, events } = render([
      { name: "r1", idx: 1, docstatus: 1, a: "1", b: "2" },
      { [ROW_ID]: "row-old", a: "3" },
    ]);
    menuItem(0, "Duplicate")!.click();
    await nextTick();
    const copy = rows.value[1];
    expect(copy).toMatchObject({ a: "1", b: "2" });
    expect(copy.name).toBeUndefined();
    expect(copy.idx).toBeUndefined();
    expect(copy.docstatus).toBeUndefined();
    expect(copy[ROW_ID]).toBeTruthy();
    expect(copy[ROW_ID]).not.toBe("row-old");
    expect(events.add).toBe(1);
  });

  it("inserts and duplicates from the keyboard, focusing the new row's cell", async () => {
    const { rows } = render(twoRows());
    input(0, 1).focus();
    press(input(0, 1), "ArrowDown", { ctrlKey: true });
    await nextTick();
    expect(rows.value.map((r) => r.name ?? "new")).toEqual(["r1", "new", "r2"]);
    expect(document.activeElement).toBe(input(1, 1));
    press(input(2, 0), "ArrowUp", { metaKey: true });
    await nextTick();
    expect(rows.value.map((r) => r.name ?? "new")).toEqual(["r1", "new", "new", "r2"]);
    press(input(0, 0), "ArrowDown", { shiftKey: true, altKey: true });
    await nextTick();
    expect(rows.value[1]).toMatchObject({ a: "1", b: "2", c: "3" });
    expect(rows.value[1].name).toBeUndefined();
  });
});

describe("Grid fast entry under cannotAddRows", () => {
  it("keeps only Edit in the row menu", () => {
    render(twoRows(), { cannotAddRows: true });
    expect(menuLabels(0)).toEqual(["Edit"]);
  });

  it("refuses the insert and duplicate keys without building a row", async () => {
    const newRow = vi.fn(() => ({}));
    const { rows } = render(twoRows(), { cannotAddRows: true, newRow });
    const event = new KeyboardEvent("keydown", {
      key: "ArrowDown",
      ctrlKey: true,
      bubbles: true,
      cancelable: true,
    });
    input(0, 0).dispatchEvent(event);
    press(input(0, 0), "ArrowDown", { shiftKey: true, altKey: true });
    await nextTick();
    expect(rows.value).toHaveLength(2);
    expect(newRow).not.toHaveBeenCalled();
    expect(event.defaultPrevented).toBe(false);
  });

  it("pastes into the rows there are and adds none", async () => {
    const { rows, events } = render(twoRows(), { cannotAddRows: true });
    paste(input(1, 0), "x\ny\nz");
    await nextTick();
    expect(rows.value.map((r) => r.a)).toEqual(["1", "x"]);
    expect(events.add).toBe(0);
  });
});
