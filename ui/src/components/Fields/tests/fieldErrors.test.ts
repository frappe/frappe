import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, provide, ref } from "vue";
import type { App, Component } from "vue";
import TableField from "../TableField.vue";
import FormLayoutColumn from "../../FormLayout/FormLayoutColumn.vue";
import { getFieldComponent } from "../fieldTypes";
import { DocKey, FieldErrorsKey, NO_COMMIT, CommitKey, UpdateKey, fieldErrorKey } from "../types";
import { ResolveFieldKey } from "../../FormLayout/types";
import type { FieldError } from "../types";

const MESSAGE = "Quantity must be positive";

const VALUE_FIELDTYPES = [
  "Data",
  "Int",
  "Long Int",
  "Float",
  "Currency",
  "Percent",
  "Small Text",
  "Text",
  "Long Text",
  "Code",
  "JSON",
  "Markdown Editor",
  "HTML Editor",
  "Text Editor",
  "Select",
  "Check",
  "Date",
  "Datetime",
  "Time",
  "Duration",
  "Phone",
  "Password",
  "Autocomplete",
  "Rating",
  "Link",
  "Dynamic Link",
  "Attach",
  "Attach Image",
  "Geolocation",
  "Read Only",
  "Table",
  "Table MultiSelect",
];

let app: App | undefined;
let host: HTMLElement | undefined;

afterEach(() => {
  app?.unmount();
  host?.remove();
  app = undefined;
  host = undefined;
  vi.useRealTimers();
});

// Provides null between the app's map and the component, as a host with no form inside a form does.
const NoForm = defineComponent({
  setup(_, { slots }) {
    provide(FieldErrorsKey, null);
    return () => slots.default?.();
  },
});

function mount(component: Component, props: Record<string, any>, errors?: any, noForm = false) {
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({
    render: () => (noForm ? h(NoForm, () => h(component, props)) : h(component, props)),
  });
  app.provide(DocKey, ref({}));
  app.provide(UpdateKey, () => {});
  app.provide(CommitKey, NO_COMMIT);
  app.provide(ResolveFieldKey, getFieldComponent);
  if (errors !== undefined) app.provide(FieldErrorsKey, errors);
  app.mount(host);
  return host;
}

describe("a control", () => {
  for (const fieldtype of VALUE_FIELDTYPES) {
    it(`draws the error its host passes: ${fieldtype}`, async () => {
      const field = { fieldname: "qty", fieldtype, label: "Qty", options: "" };
      const el = mount(getFieldComponent(fieldtype), { field, modelValue: null, error: MESSAGE });
      await vi.waitFor(() => expect(el.textContent).toContain(MESSAGE));
    });
  }

  for (const fieldtype of ["Link", "Dynamic Link"]) {
    it(`draws the error on a read-only ${fieldtype} in place of its description`, () => {
      const field = { fieldname: "customer", fieldtype, label: "Customer", description: "Who pays", readOnly: true };
      const el = mount(getFieldComponent(fieldtype), { field, modelValue: "C-1", error: MESSAGE });
      expect(el.querySelector('[data-slot="link-value"]')).not.toBeNull();
      expect(el.textContent).toContain(MESSAGE);
      expect(el.textContent).not.toContain("Who pays");
    });
  }

  it("links a code editor to its error rather than its hidden description", async () => {
    const field = { fieldname: "script", fieldtype: "Code", label: "Script", description: "Runs on save" };
    const el = mount(getFieldComponent("Code"), { field, modelValue: "", error: MESSAGE });
    await vi.waitFor(() => expect(el.querySelector(".cm-content")).not.toBeNull());
    const content = el.querySelector(".cm-content")!;
    const alert = el.querySelector('[role="alert"]')!;
    expect(el.textContent).not.toContain("Runs on save");
    expect(content.getAttribute("aria-describedby")).toBe(alert.id);
    expect(content.getAttribute("aria-invalid")).toBe("true");
  });

  it("stacks several messages", () => {
    const field = { fieldname: "qty", fieldtype: "Data", label: "Qty" };
    const el = mount(getFieldComponent("Data"), {
      field,
      modelValue: null,
      error: [MESSAGE, "Quantity must be whole"],
    });
    expect(el.textContent).toContain(MESSAGE);
    expect(el.textContent).toContain("Quantity must be whole");
  });
});

describe("a form field", () => {
  const column = {
    fields: [
      { fieldname: "qty", fieldtype: "Data", label: "Qty" },
      { fieldname: "rate", fieldtype: "Data", label: "Rate" },
    ],
  };

  it("draws the error its host's map holds for it, and only for it", () => {
    const el = mount(FormLayoutColumn, { column }, ref({ [fieldErrorKey("qty")]: MESSAGE }));
    expect(el.querySelector('[data-fieldname="qty"]')!.textContent).toContain(MESSAGE);
    expect(el.querySelector('[data-fieldname="rate"]')!.textContent).not.toContain(MESSAGE);
  });

  it("draws nothing when its host provides null inside a form that has errors", () => {
    const el = mount(FormLayoutColumn, { column }, ref({ qty: MESSAGE }), true);
    expect(el.textContent).not.toContain(MESSAGE);
  });

  it("clears when its host removes the error", async () => {
    const errors = ref<Record<string, FieldError>>({ qty: MESSAGE });
    const el = mount(FormLayoutColumn, { column }, errors);
    errors.value = {};
    await nextTick();
    expect(el.textContent).not.toContain(MESSAGE);
  });
});

describe("a grid cell", () => {
  const field = {
    fieldname: "items",
    fieldtype: "Table",
    label: "Items",
    childFields: [
      { fieldname: "qty", fieldtype: "Data", label: "Qty" },
      { fieldname: "rate", fieldtype: "Data", label: "Rate" },
    ],
  };
  const rows = [{ name: "r1" }, { name: "r2" }];
  const qtyOfR2 = fieldErrorKey({ parentfield: "items", key: "name:r2", fieldname: "qty" });

  function cell(el: HTMLElement, row: string, fieldname: string): HTMLElement {
    return el.querySelector(`[data-name="${row}"] [data-fieldname="${fieldname}"]`)!;
  }

  it("rings the cell its error names, and no other", () => {
    const el = mount(TableField, { field, modelValue: rows }, ref({ [qtyOfR2]: MESSAGE }));
    expect(cell(el, "r2", "qty").hasAttribute("data-invalid")).toBe(true);
    expect(cell(el, "r2", "rate").hasAttribute("data-invalid")).toBe(false);
    expect(cell(el, "r1", "qty").hasAttribute("data-invalid")).toBe(false);
  });

  it("rings and clears a cell under a focused input without rebuilding it", async () => {
    const errors = ref<Record<string, FieldError>>({});
    const el = mount(TableField, { field, modelValue: rows }, errors);
    const input = cell(el, "r2", "qty").querySelector("input")!;
    input.focus();

    errors.value = { [qtyOfR2]: MESSAGE };
    await nextTick();
    expect(cell(el, "r2", "qty").hasAttribute("data-invalid")).toBe(true);
    expect(document.activeElement).toBe(input);

    errors.value = {};
    await nextTick();
    expect(cell(el, "r2", "qty").hasAttribute("data-invalid")).toBe(false);
    expect(document.activeElement).toBe(input);
  });

  it("keeps the message out of the row and shows it as a tooltip", async () => {
    vi.useFakeTimers();
    const el = mount(TableField, { field, modelValue: rows }, ref({ [qtyOfR2]: MESSAGE }));
    expect(el.textContent).not.toContain(MESSAGE);

    cell(el, "r2", "qty").dispatchEvent(new PointerEvent("pointermove", { pointerType: "mouse" }));
    await vi.advanceTimersByTimeAsync(1000);
    expect(document.body.querySelector('[data-slot="content"]')?.textContent).toContain(MESSAGE);
  });

  it("rings nothing when its host provides null inside a form that has errors", () => {
    const el = mount(TableField, { field, modelValue: rows }, ref({ [qtyOfR2]: MESSAGE }), true);
    expect(el.querySelector("[data-invalid]")).toBeNull();
  });
});
