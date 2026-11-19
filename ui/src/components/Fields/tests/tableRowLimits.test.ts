import { afterEach, describe, expect, it } from "vitest";
import { createApp, defineComponent, h, nextTick } from "vue";
import type { App } from "vue";
import TableField from "../TableField.vue";
import { ResolveFieldKey } from "../../FormLayout/types";
import type { FieldMeta } from "../types";

const StubField = defineComponent({ setup: () => () => h("input") });

let app: App | undefined;
let host: HTMLElement | undefined;

afterEach(() => {
  app?.unmount();
  host?.remove();
  app = undefined;
  host = undefined;
});

function render(limits: Pick<FieldMeta, "cannotAddRows" | "cannotDeleteRows">) {
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({
    render: () =>
      h(TableField, {
        field: {
          fieldname: "products",
          fieldtype: "Table",
          childFields: [{ fieldname: "qty", fieldtype: "Data" }],
          ...limits,
        },
        modelValue: [{ name: "a", qty: 1 }],
      }),
  });
  app.provide(ResolveFieldKey, () => StubField);
  app.mount(host);
}

function labels(): string[] {
  return [...host!.querySelectorAll("button")].map((b) => b.textContent?.trim() ?? "");
}

async function selectAll() {
  host!
    .querySelector<HTMLElement>('[aria-label="Select all"]')!
    .dispatchEvent(new MouseEvent("click", { bubbles: true }));
  await nextTick();
}

describe("TableField row limits", () => {
  it("drops Add Row when the Table field has cannotAddRows", () => {
    render({ cannotAddRows: true });
    expect(labels()).not.toContain("Add Row");
  });

  it("drops Delete for a selection when the Table field has cannotDeleteRows", async () => {
    render({ cannotDeleteRows: true });
    await selectAll();
    expect(labels()).toContain("Add Row");
    expect(labels().some((label) => label.startsWith("Delete"))).toBe(false);
  });
});

describe("TableField columns", () => {
  it("drops a column a script hides, header and cells", () => {
    host = document.createElement("div");
    document.body.appendChild(host);
    app = createApp({
      render: () =>
        h(TableField, {
          field: {
            fieldname: "products",
            fieldtype: "Table",
            childFields: [
              { fieldname: "qty", fieldtype: "Data", label: "Qty" },
              { fieldname: "rate", fieldtype: "Data", label: "Rate", override: { hidden: true } },
            ],
          },
          modelValue: [{ name: "a", qty: 1, rate: 2 }],
        }),
    });
    app.provide(ResolveFieldKey, () => StubField);
    app.mount(host);
    expect(host.textContent).toContain("Qty");
    expect(host.textContent).not.toContain("Rate");
  });
});
