import { describe, expect, it } from "vitest";
import { createApp, h } from "vue";
import TableField from "../TableField.vue";
import { getFieldComponent } from "../fieldTypes";
import { gridColumnWidth } from "../gridColumnWidth";
import { ResolveFieldKey } from "../../FormLayout/types";

describe("gridColumnWidth", () => {
  it("maps `columns` to desk v1's pixel widths", () => {
    const widths = Array.from({ length: 10 }, (_, i) =>
      gridColumnWidth({ fieldtype: "Data", gridColumns: i + 1 })
    );
    expect(widths).toEqual([60, 100, 140, 200, 250, 300, 350, 400, 450, 500]);
  });

  it("gives an Auto column its fieldtype's default", () => {
    expect(gridColumnWidth({ fieldtype: "Check" })).toBe(60);
    expect(gridColumnWidth({ fieldtype: "Currency" })).toBe(100);
    expect(gridColumnWidth({ fieldtype: "Small Text" })).toBe(200);
    expect(gridColumnWidth({ fieldtype: "Link" })).toBe(140);
  });

  it("lets `columns` win over the fieldtype", () => {
    expect(gridColumnWidth({ fieldtype: "Check", gridColumns: 4 })).toBe(200);
  });

  it("reads a width off v1's map as Auto", () => {
    expect(gridColumnWidth({ fieldtype: "Int", gridColumns: 13 })).toBe(100);
  });
});

describe("A Table grid", () => {
  it("draws each column at its `columns` width, Auto at its fieldtype's", () => {
    const host = document.createElement("div");
    document.body.appendChild(host);
    const field = {
      fieldname: "items",
      fieldtype: "Table",
      childFields: [
        { fieldname: "item", fieldtype: "Link", label: "Item", gridColumns: 4 },
        { fieldname: "qty", fieldtype: "Float", label: "Qty" },
      ],
    };
    const app = createApp({ render: () => h(TableField, { field, modelValue: [] }) });
    app.provide(ResolveFieldKey, getFieldComponent);
    app.mount(host);
    const header = host.querySelector<HTMLElement>(".grid-scroller > div")!;
    expect(header.style.gridTemplateColumns).toContain("minmax(200px, 200fr) minmax(100px, 100fr)");
    app.unmount();
    host.remove();
  });
});
