// FieldBox draws the row's hover, focus and error looks; a panel control draws no label, description or error text.
import { afterEach, describe, expect, it } from "vitest";
import { createApp, h } from "vue";
import type { App, Component } from "vue";
import FieldBox from "../FieldBox.vue";
import TextField from "../TextField.vue";
import NumberField from "../NumberField.vue";
import PhoneField from "../PhoneField.vue";
import PasswordField from "../PasswordField.vue";
import DurationField from "../DurationField.vue";
import type { FieldMeta } from "../types";

let app: App | undefined;
let host: HTMLElement | undefined;

afterEach(() => {
  app?.unmount();
  host?.remove();
  app = host = undefined;
});

function mount(component: Component, props: Record<string, unknown>) {
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({ render: () => h(component, props, () => h("input")) });
  app.mount(host);
  return host;
}

describe("FieldBox", () => {
  it("takes the hover fill only when interactive", () => {
    expect(mount(FieldBox, { interactive: true }).firstElementChild!.className).toContain(
      "hover:bg-surface-gray-2"
    );
    app!.unmount();
    expect(mount(FieldBox, {}).firstElementChild!.className).not.toContain("hover:bg-surface-gray-2");
  });

  it("keeps the hover fill on focus and adds the inset gray ring", () => {
    const box = mount(FieldBox, {}).firstElementChild!;
    expect(box.className).toContain("focus-within:bg-surface-gray-2");
    expect(box.className).toContain("focus-within:ring-inset");
    expect(box.className).toContain("focus-within:ring-outline-gray-3");
  });

  it("rings red on focus when it holds an error", () => {
    const box = mount(FieldBox, { error: true }).firstElementChild!;
    expect(box.className).toContain("focus-within:ring-outline-red-3");
    expect(box.className).not.toContain("focus-within:ring-outline-gray-3");
  });
});

const field = (fieldtype: string): FieldMeta => ({
  fieldname: "f",
  fieldtype,
  label: "Label F",
  description: "A description",
  placeholder: "Add Label F...",
});

describe.each([
  ["Data", TextField],
  ["Int", NumberField],
  ["Phone", PhoneField],
  ["Password", PasswordField],
  ["Duration", DurationField],
])("%s in panel mode", (fieldtype, component) => {
  const props = { field: field(fieldtype), modelValue: "1", error: "Bad value" };

  it("draws no label, description or error text, and keeps the placeholder", () => {
    const el = mount(component, { ...props, panel: true });
    expect(el.querySelector("label")).toBeNull();
    expect(el.textContent).not.toContain("Label F");
    expect(el.textContent).not.toContain("A description");
    expect(el.textContent).not.toContain("Bad value");
    expect(el.querySelector("input")!.getAttribute("placeholder")).toBe("Add Label F...");
  });

  it("is a ghost box 28 high that is marked invalid", () => {
    const input = mount(component, { ...props, panel: true }).querySelector("input")!;
    expect(input.className).toContain("border-0");
    expect(input.className).toContain("h-7");
    expect(input.getAttribute("aria-invalid")).toBe("true");
  });

  it("still draws its label, description and error text outside a panel", () => {
    const el = mount(component, props);
    expect(el.textContent).toContain("Label F");
    expect(el.textContent).toContain("Bad value");
  });
});
