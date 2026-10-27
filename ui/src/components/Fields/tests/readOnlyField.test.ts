// A field the user cannot edit draws its formatted value, not a disabled control.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, ref } from "vue";
import type { App } from "vue";

vi.mock("frappe-ui", async (importOriginal) => {
  const real = (await importOriginal()) as Record<string, unknown>;
  return {
    ...real,
    Dialog: defineComponent({
      props: { open: { type: Boolean, default: false } },
      setup: (props, { slots }) => () =>
        props.open ? h("div", { "data-dialog": "" }, slots.default?.()) : null,
    }),
  };
});
import FormLayoutField from "../../FormLayout/FormLayoutField.vue";
import TableField from "../TableField.vue";
import { getFieldComponent } from "../fieldTypes";
import { CommitKey, DocKey, NO_COMMIT, UpdateKey } from "../types";
import { ResolveFieldKey } from "../../FormLayout/types";
import { setFormatDefaults, resetFormatDefaults } from "../../FormLayout/formatDefaults";
import type { FieldNode } from "../../FormLayout/types";

let app: App | undefined;
let host: HTMLElement | undefined;

afterEach(() => {
  app?.unmount();
  host?.remove();
  app = host = undefined;
  resetFormatDefaults();
});

function mount(field: Partial<FieldNode>, doc: Record<string, any>): HTMLElement {
  const node = { fieldname: "f", label: "F", ...field } as FieldNode;
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({ render: () => h(FormLayoutField, { field: node }) });
  app.provide(DocKey, ref(doc));
  app.provide(UpdateKey, () => {});
  app.provide(CommitKey, NO_COMMIT);
  app.provide(ResolveFieldKey, getFieldComponent);
  app.mount(host);
  return host;
}

const readValue = (el: HTMLElement) => el.querySelector("[data-slot='read-value']");

describe("a field the user cannot edit", () => {
  const cases: [string, Partial<FieldNode>, unknown, string][] = [
    ["Read Only", {}, "IBAN DE89", "IBAN DE89"],
    ["Data", {}, "Ada", "Ada"],
    ["Int", {}, 1234567, "1234567"],
    ["Float", { precision: 2 }, 1234.5, "1,234.50"],
    ["Currency", { options: "" }, 1500.5, "₹ 1,500.50"],
    ["Select", { options: "Open\nClosed" }, "Closed", "Closed"],
    ["Time", {}, "9:15:00", "09:15"],
    ["Password", {}, "secret", "••••••••"],
    ["Datetime", {}, "2026-10-24 09:15:00.123456", "2026-10-24 09:15:00"],
    ["Int", {}, null, "0"],
    ["Currency", { options: "" }, null, "₹ 0.00"],
  ];
  for (const [fieldtype, extra, value, shown] of cases) {
    it(`draws a read-only ${fieldtype} as its formatted value, with no input`, () => {
      setFormatDefaults({ number_format: "#,###.##", currency: "INR" });
      const el = mount({ fieldtype, readOnly: true, ...extra }, { f: value });
      expect(readValue(el)?.textContent?.trim()).toBe(shown);
      expect(el.querySelector("input, textarea, select, button")).toBeNull();
      expect(el.textContent).toContain("F");
    });
  }

  it("draws a Read Only field with no readOnly flag as its value", () => {
    const el = mount({ fieldtype: "Read Only" }, { f: "Ada" });
    expect(readValue(el)?.textContent?.trim()).toBe("Ada");
    expect(el.querySelector("input")).toBeNull();
  });

  it("draws an un-locked Read Only field as an input", () => {
    const el = mount({ fieldtype: "Read Only", readOnly: false }, { f: "Ada" });
    expect(readValue(el)).toBeNull();
    expect((el.querySelector("input") as HTMLInputElement | null)?.value).toBe("Ada");
  });

  it("falls back to the site's float and currency precision", () => {
    setFormatDefaults({ number_format: "#,###.##", currency: "INR", float_precision: 3, currency_precision: 0 });
    const float = mount({ fieldtype: "Float", readOnly: true }, { f: 1234.5 });
    expect(readValue(float)?.textContent?.trim()).toBe("1,234.500");
    app?.unmount();
    const currency = mount({ fieldtype: "Currency", options: "", readOnly: true }, { f: 1500.5 });
    expect(readValue(currency)?.textContent?.trim()).toBe("₹ 1,500");
  });

  it("keeps a read-only Link's title anchor", () => {
    const el = mount({ fieldtype: "Link", options: "User", readOnly: true }, { f: "ada@x.com" });
    expect(readValue(el)).toBeNull();
    expect(el.querySelector("[data-slot='link-value']")).not.toBeNull();
  });

  it("draws a field above the user's permlevel the same way", () => {
    const el = mount({ fieldtype: "Data", readOnly: true, permDenied: true, permlevel: 1 }, { f: "x" });
    expect(readValue(el)?.textContent?.trim()).toBe("x");
  });

  it("keeps an editable field's control", () => {
    const el = mount({ fieldtype: "Data" }, { f: "x" });
    expect(readValue(el)).toBeNull();
    expect(el.querySelector("input")).not.toBeNull();
  });

  it("keeps a ui.component that replaces the control", () => {
    const Custom = { render: () => h("i", { "data-custom": "" }) };
    const el = mount({ fieldtype: "Data", readOnly: true, ui: { component: Custom } }, { f: "x" });
    expect(el.querySelector("[data-custom]")).not.toBeNull();
    expect(readValue(el)).toBeNull();
  });
});

describe("a control with its own read view keeps it when read-only", () => {
  it("Check", () => {
    const el = mount({ fieldtype: "Check", readOnly: true }, { f: 1 });
    expect(readValue(el)).toBeNull();
    expect(el.querySelector("input[type='checkbox']")).not.toBeNull();
  });

  it("Rating", () => {
    const el = mount({ fieldtype: "Rating", readOnly: true }, { f: 0.6 });
    expect(readValue(el)).toBeNull();
    expect(el.querySelectorAll("svg, button").length).toBeGreaterThan(0);
  });

  it("Text Editor", () => {
    const el = mount({ fieldtype: "Text Editor", readOnly: true }, { f: "<p>Hi</p>" });
    expect(readValue(el)).toBeNull();
    expect(el.querySelector("[data-slot='text-editor-value']")).not.toBeNull();
  });
});

describe("a read-only Attach Image keeps its own view", () => {
  it("draws the image, not a text box", () => {
    const el = mount({ fieldtype: "Attach Image", readOnly: true }, { f: "/files/logo.png" });
    expect(readValue(el)).toBeNull();
    expect(el.querySelector("img")?.getAttribute("src")).toContain("/files/logo.png");
  });
});

describe("a read-only multi-line text", () => {
  it("draws every line in the form", () => {
    const el = mount({ fieldtype: "Small Text", readOnly: true }, { f: "one\ntwo" });
    expect(readValue(el)?.textContent).toContain("one\ntwo");
    expect(el.querySelector("textarea")).toBeNull();
  });
});

describe("a read-only code field", () => {
  it("keeps the code view and drops the five-line minimum", async () => {
    const el = mount({ fieldtype: "Code", options: "JavaScript", readOnly: true }, { f: "let a = 1;" });
    await vi.waitFor(() => expect(el.querySelector(".cm-editor")).not.toBeNull());
    expect(el.querySelector(".code-content")?.classList.contains("code-fit")).toBe(true);
    expect(el.querySelector(".cm-content")?.getAttribute("contenteditable")).toBe("false");
  });

  it("an editable one keeps the minimum", async () => {
    const el = mount({ fieldtype: "Code", options: "JavaScript" }, { f: "" });
    await vi.waitFor(() => expect(el.querySelector(".cm-editor")).not.toBeNull());
    expect(el.querySelector(".code-content")?.classList.contains("code-fit")).toBe(false);
  });

  it('shows "Not set" when empty, with no editor', async () => {
    const el = mount({ fieldtype: "JSON", readOnly: true }, { f: "" });
    await vi.waitFor(() => expect(readValue(el)?.textContent?.trim()).toBe("Not set"));
    expect(el.querySelector(".cm-editor")).toBeNull();
  });
});

describe("a read-only table", () => {
  const childFields = [
    { fieldname: "qty", fieldtype: "Float", label: "Qty", precision: 2 },
    { fieldname: "amount", fieldtype: "Currency", label: "Amount", options: "currency" },
  ];

  function mountTable(rows: Record<string, any>[], doc: Record<string, any> = {}): HTMLElement {
    const field = { fieldname: "items", fieldtype: "Table", label: "Items", readOnly: true, childFields };
    host = document.createElement("div");
    document.body.appendChild(host);
    app = createApp({ render: () => h(TableField, { field, modelValue: rows }) });
    app.provide(DocKey, ref(doc));
    app.provide(UpdateKey, () => {});
    app.provide(CommitKey, NO_COMMIT);
    app.provide(ResolveFieldKey, getFieldComponent);
    app.mount(host);
    return host;
  }

  const cellText = (el: HTMLElement, fieldname: string) =>
    el.querySelector(`.grid-cell[data-fieldname='${fieldname}'] [data-slot='read-value']`)?.textContent?.trim();

  it("draws a cell's formatted value, the same string as the form", () => {
    setFormatDefaults({ number_format: "#,###.##" });
    const el = mountTable([{ name: "r1", qty: 4200 }]);
    expect(cellText(el, "qty")).toBe("4,200.00");
    expect(el.querySelector(".grid-cell[data-fieldname='qty'] input")).toBeNull();
  });

  it("draws a multi-line text cell as its value, with no textarea", () => {
    const field = {
      fieldname: "items", fieldtype: "Table", label: "Items", readOnly: true,
      childFields: [{ fieldname: "notes", fieldtype: "Text", label: "Notes" }],
    };
    host = document.createElement("div");
    document.body.appendChild(host);
    app = createApp({ render: () => h(TableField, { field, modelValue: [{ name: "r1", notes: "one\ntwo" }] }) });
    app.provide(DocKey, ref({}));
    app.provide(UpdateKey, () => {});
    app.provide(CommitKey, NO_COMMIT);
    app.provide(ResolveFieldKey, getFieldComponent);
    app.mount(host);
    expect(cellText(host, "notes")).toBe("one\ntwo");
    expect(host.querySelector(".grid-cell[data-fieldname='notes'] textarea")).toBeNull();
  });

  it("formats a cell's Currency in the row's currency, else the parent's", () => {
    setFormatDefaults({ number_format: "#,###.##", currency: "INR" });
    const fromRow = mountTable([{ name: "r1", amount: 10, currency: "USD" }], { currency: "EUR" });
    expect(cellText(fromRow, "amount")).toBe("$ 10.00");
    app?.unmount();
    const fromParent = mountTable([{ name: "r1", amount: 10 }], { currency: "EUR" });
    expect(cellText(fromParent, "amount")).toBe("€ 10.00");
  });

  it("draws the row dialog's fields as values, in the parent's currency", async () => {
    setFormatDefaults({ number_format: "#,###.##", currency: "INR" });
    const el = mountTable([{ name: "r1", qty: 4200, amount: 10 }], { currency: "EUR" });
    (el.querySelector(".grid-cell[data-fieldname='qty']") as HTMLElement).click();
    const values = () =>
      [...el.querySelectorAll("[data-dialog] [data-slot='read-value']")].map((v) => v.textContent?.trim());
    await vi.waitFor(() => expect(values()).toEqual(["4,200.00", "€ 10.00"]));
    expect(el.querySelector("[data-dialog] input")).toBeNull();
  });
});
