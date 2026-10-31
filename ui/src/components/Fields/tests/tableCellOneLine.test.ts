import { afterEach, describe, expect, it } from "vitest";
import { createApp, defineComponent, h } from "vue";
import type { App } from "vue";
import TableField from "../TableField.vue";
import { getFieldComponent } from "../fieldTypes";
import { ResolveFieldKey } from "../../FormLayout/types";

let app: App | undefined;
let host: HTMLElement | undefined;

afterEach(() => {
  app?.unmount();
  host?.remove();
  app = undefined;
  host = undefined;
});

function render(fieldtype: string, notes: string, ui?: Record<string, any>) {
  host = document.createElement("div");
  document.body.appendChild(host);
  const field = {
    fieldname: "items",
    fieldtype: "Table",
    childFields: [{ fieldname: "notes", fieldtype, label: "Notes", ui }],
  };
  app = createApp({
    render: () => h(TableField, { field, modelValue: [{ name: "r1", notes }] }),
  });
  app.provide(ResolveFieldKey, getFieldComponent);
  app.mount(host);
  return host.querySelector<HTMLElement>('[data-fieldname="notes"]')!;
}

describe("A multi-line text cell", () => {
  for (const fieldtype of ["Small Text", "Text", "Long Text"]) {
    it(`shows a ${fieldtype} value on one line over its textarea`, () => {
      const cell = render(fieldtype, "first line\nsecond line");
      const preview = cell.querySelector<HTMLElement>(".grid-one-line")!;
      expect(preview.dataset.preview).toBe("first line second line");
      expect(preview.querySelector("textarea")!.value).toBe("first line\nsecond line");
    });
  }

  it("leaves a single-line cell without a preview", () => {
    const cell = render("Data", "first line");
    expect(cell.querySelector(".grid-one-line")).toBeNull();
  });

  it("leaves a script's own component without a preview", () => {
    const Own = defineComponent({ setup: () => () => h("span", "own") });
    const cell = render("Small Text", "first line\nsecond line", { component: Own });
    expect(cell.querySelector(".grid-one-line")).toBeNull();
    expect(cell.textContent).toBe("own");
  });
});
