import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, ref } from "vue";
import type { App } from "vue";

// The real menu opens in a portal on pointer events; the stub draws its items as buttons.
vi.mock("frappe-ui", async (importOriginal) => {
  const actual = await importOriginal<typeof import("frappe-ui")>();
  const Dropdown = defineComponent({
    props: ["options"],
    setup(props, { slots }) {
      return () =>
        h("div", { "data-dropdown": "" }, [
          slots.default?.(),
          ...props.options.map((o: any) =>
            h("button", { "data-menu-item": o.label, onClick: o.onClick }, o.label)
          ),
        ]);
    },
  });
  return { ...actual, Dropdown };
});

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

  it("leaves a single value to the input's own paste", () => {
    const { events } = render(twoRows());
    const event = paste(input(0, 0), "just one\n");
    expect(event.defaultPrevented).toBe(false);
    expect(events.commit).toEqual([]);
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
      { name: "r1", idx: 1, a: "1", b: "2" },
      { [ROW_ID]: "row-old", a: "3" },
    ]);
    menuItem(0, "Duplicate")!.click();
    await nextTick();
    const copy = rows.value[1];
    expect(copy).toMatchObject({ a: "1", b: "2" });
    expect(copy.name).toBeUndefined();
    expect(copy.idx).toBeUndefined();
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
  it("shows no row menu", () => {
    render(twoRows(), { cannotAddRows: true });
    expect(host!.querySelector("[data-dropdown]")).toBeNull();
    expect(host!.querySelector('[aria-label="Edit Row"]')).not.toBeNull();
  });

  it("refuses the insert and duplicate keys", async () => {
    const { rows } = render(twoRows(), { cannotAddRows: true });
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
