import { afterEach, describe, expect, it } from "vitest";
import { createApp, h, nextTick, ref } from "vue";
import type { App } from "vue";
import Grid from "../Grid.vue";
import { ROW_ID } from "../../Fields/rowIdentity";
import type { GridColumn } from "../types";

let app: App | undefined;
let host: HTMLElement | undefined;

afterEach(() => {
  app?.unmount();
  host?.remove();
  app = undefined;
  host = undefined;
});

function render(columns: GridColumn[], rows: Record<string, any>[] = []) {
  return renderRows(columns, ref(rows));
}

function renderRows(columns: GridColumn[], rows: { value: Record<string, any>[] }) {
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({ render: () => h(Grid, { columns, modelValue: rows.value }) });
  app.mount(host);
  return host;
}

function manyColumns(count: number): GridColumn[] {
  return Array.from({ length: count }, (_, i) => ({ fieldname: `col_${i}` }));
}

describe("Grid columns", () => {
  it("keeps a flexible column at least 128px wide", () => {
    const grid = render(manyColumns(3));
    const header = grid.querySelector<HTMLElement>(".grid-scroller > div")!;
    expect(header.style.gridTemplateColumns).toContain("minmax(128px, 1fr)");
    expect(header.style.gridTemplateColumns).not.toContain("minmax(0, 1fr)");
  });

  it("widens the rows past the viewport so many columns scroll sideways", () => {
    const grid = render(manyColumns(38), [{ name: "r1" }]);
    const row = grid.querySelector<HTMLElement>(".grid-row")!;
    expect(row.style.minWidth).toBe(`calc(7.5rem + ${38 * 128}px)`);
  });

  it("counts a resized column at its own width", () => {
    const grid = render([{ fieldname: "a", width: 60 }, { fieldname: "b" }], [{ name: "r1" }]);
    const row = grid.querySelector<HTMLElement>(".grid-row")!;
    expect(row.style.gridTemplateColumns).toContain("60px minmax(128px, 1fr)");
    expect(row.style.minWidth).toBe(`calc(7.5rem + ${60 + 128}px)`);
  });
});

describe("Grid handles", () => {
  it("marks each row with its name and position", () => {
    const grid = render([{ fieldname: "qty" }], [{ name: "a1b2" }, { name: "c3d4" }]);
    const rows = [...grid.querySelectorAll<HTMLElement>(".grid-row")];
    expect(rows.map((row) => [row.dataset.name, row.dataset.idx])).toEqual([
      ["a1b2", "1"],
      ["c3d4", "2"],
    ]);
  });

  it("renumbers the rows after a reorder", async () => {
    const rows = ref([{ name: "a1b2" }, { name: "c3d4" }]);
    const grid = renderRows([{ fieldname: "qty" }], rows);
    rows.value = [rows.value[1], rows.value[0]];
    await nextTick();
    const row = grid.querySelector<HTMLElement>('[data-name="c3d4"]')!;
    expect(row.dataset.idx).toBe("1");
  });

  it("names an unsaved row by its client id", () => {
    const grid = render([{ fieldname: "qty" }], [{ [ROW_ID]: "row-7" }]);
    expect(grid.querySelector<HTMLElement>(".grid-row")!.dataset.name).toBe("row-7");
  });

  it("marks each cell with its fieldname and fieldtype", () => {
    const grid = render(
      [
        { fieldname: "qty", fieldtype: "Int" },
        { fieldname: "notes", fieldtype: "Small Text" },
      ],
      [{ name: "a1b2" }]
    );
    const cells = [...grid.querySelectorAll<HTMLElement>('[data-name="a1b2"] .grid-cell')];
    expect(cells.map((cell) => [cell.dataset.fieldname, cell.dataset.fieldtype])).toEqual([
      ["qty", "Int"],
      ["notes", "Small Text"],
    ]);
  });
});
