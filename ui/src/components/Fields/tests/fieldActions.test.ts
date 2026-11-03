// A Phone control draws the actions the host hands it through `FieldActionsKey`: one is an icon button, two or more a menu.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h } from "vue";
import type { App, Component } from "vue";
import PhoneField from "../PhoneField.vue";
import ReadOnlyField from "../ReadOnlyField.vue";
import TextField from "../TextField.vue";
import { FieldActionsKey } from "../types";
import type { FieldAction, FieldActions, FieldMeta } from "../types";

let app: App | undefined;
let host: HTMLElement | undefined;

afterEach(() => {
  app?.unmount();
  host?.remove();
  app = undefined;
  host = undefined;
});

function action(label: string, run = vi.fn()): FieldAction {
  return { act: `shell.crm.${label}`, label, icon: "lucide-phone", run };
}

function render(
  component: Component,
  field: FieldMeta,
  value: string | null,
  actions: FieldAction[] | null,
  props: Record<string, unknown> = {}
) {
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({ render: () => h(component, { field, modelValue: value, ...props }) });
  const fieldActions: FieldActions = { for: (_field, current) => (current ? actions ?? [] : []) };
  if (actions) app.provide(FieldActionsKey, fieldActions);
  app.mount(host);
  return host;
}

const phone: FieldMeta = { fieldname: "mobile_no", fieldtype: "Phone", label: "Mobile" };
const dataPhone: FieldMeta = { fieldname: "mobile_no", fieldtype: "Data", options: "Phone" };

describe("field actions on a phone control", () => {
  it("draw one action as an icon button that runs it", async () => {
    const run = vi.fn();
    const root = render(PhoneField, phone, "123", [action("Call", run)]);

    const button = root.querySelector<HTMLElement>('[data-slot="field-action"]')!;
    button.click();

    expect(button.getAttribute("aria-label")).toBe("Call");
    expect(run).toHaveBeenCalledTimes(1);
  });

  it("draw two or more as one menu button", () => {
    const root = render(PhoneField, phone, "123", [action("Call"), action("Text")]);

    expect(root.querySelector('[data-slot="field-actions"]')).not.toBeNull();
    expect(root.querySelector('[data-slot="field-action"]')).toBeNull();
  });

  it("draw none for an empty value or with no host", () => {
    expect(render(PhoneField, phone, "", [action("Call")]).querySelector("button")).toBeNull();
    app?.unmount();
    host?.remove();
    expect(render(PhoneField, phone, "123", null).querySelector("button")).toBeNull();
  });

  it("draw on a read-only field, which the record page draws as a read value", () => {
    const readOnly = { ...phone, readOnly: true };
    const root = render(ReadOnlyField, readOnly, "123", [action("Call")]);
    expect(root.querySelector('[data-slot="field-action"]')).not.toBeNull();
    app?.unmount();
    host?.remove();
    const data = { ...dataPhone, readOnly: true };
    expect(render(ReadOnlyField, data, "123", [action("Call")]).querySelector('[data-slot="field-action"]')).not.toBeNull();
    app?.unmount();
    host?.remove();
    expect(render(ReadOnlyField, readOnly, "123", [action("Call")], { row: { name: "r1" } }).querySelector("button")).toBeNull();
  });

  it("draw on a Data field whose options say Phone", () => {
    const root = render(TextField, dataPhone, "123", [action("Call")]);

    expect(root.querySelector('[data-slot="field-action"]')).not.toBeNull();
  });

  it("draw none in a grid cell, which passes its row", () => {
    const row = { name: "r1" };
    expect(render(PhoneField, phone, "123", [action("Call")], { row }).querySelector("button")).toBeNull();
    app?.unmount();
    host?.remove();
    expect(render(TextField, dataPhone, "123", [action("Call")], { row }).querySelector("button")).toBeNull();
  });

  it("leave a plain Data field alone", () => {
    const root = render(TextField, { fieldname: "title", fieldtype: "Data" }, "123", [action("Call")]);

    expect(root.querySelector("button")).toBeNull();
  });
});
