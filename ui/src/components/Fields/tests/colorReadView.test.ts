// A Color field the user cannot edit shows its swatch beside the hex, as the form, grid and row dialog draw it.
import { afterEach, describe, expect, it } from "vitest";
import { createApp, h } from "vue";
import type { App } from "vue";
import ReadOnlyField from "../ReadOnlyField.vue";
import type { FieldMeta } from "../types";

let app: App | undefined;
let host: HTMLElement | undefined;

afterEach(() => {
  app?.unmount();
  host?.remove();
  app = undefined;
  host = undefined;
});

function renderReadOnly(value: unknown, fieldtype = "Color"): HTMLElement {
  const field: FieldMeta = { fieldname: "color", fieldtype, label: "Color", readOnly: true };
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({ render: () => h(ReadOnlyField, { field, modelValue: value }) });
  app.mount(host);
  return host;
}

function swatch(el: HTMLElement): HTMLElement | null {
  return el.querySelector("[data-slot='swatch']");
}

describe("a read-only Color field", () => {
  it("draws its swatch and its hex", () => {
    const el = renderReadOnly("#268c5c");
    expect(swatch(el)?.style.backgroundColor).toBeTruthy();
    expect(el.querySelector("[data-slot='read-value']")?.textContent?.trim()).toBe("#268c5c");
  });

  it.each([["", ""], [null, ""], ["red", "red"]])("draws no swatch for %s", (value, text) => {
    const el = renderReadOnly(value);
    expect(swatch(el)).toBeNull();
    expect(el.querySelector("[data-slot='read-value']")?.textContent?.trim()).toBe(text);
  });

  it("draws no swatch for a hex in another fieldtype", () => {
    expect(swatch(renderReadOnly("#268c5c", "Data"))).toBeNull();
  });
});
