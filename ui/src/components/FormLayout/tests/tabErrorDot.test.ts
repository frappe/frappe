import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, ref } from "vue";
import type { App } from "vue";
import FormLayout from "../FormLayout.vue";
import { FieldErrorsKey, NO_COMMIT, CommitKey } from "../../Fields/types";
import type { FieldError } from "../../Fields/types";
import type { FormLayoutSchema } from "../types";

// A tab that holds a marked field shows a red dot. `Tabs` is stubbed to draw each
// trigger with its suffix, because reka-ui paints nothing under happy-dom.
vi.mock("frappe-ui", async (importOriginal) => ({
  ...((await importOriginal()) as object),
  Tabs: defineComponent({
    props: { tabs: { type: Array, required: true }, modelValue: [String, Number] },
    setup(props, { slots }) {
      return () =>
        h(
          "div",
          (props.tabs as any[]).map((tab) =>
            h("button", { "data-tab": tab.identity }, slots["tab-suffix"]?.({ tab }))
          )
        );
    },
  }),
}));

let app: App | undefined;
let host: HTMLElement | undefined;

afterEach(() => {
  app?.unmount();
  host?.remove();
});

const LAYOUT: FormLayoutSchema = [
  {
    name: "details",
    label: "Details",
    sections: [{ columns: [{ fields: [{ fieldname: "customer", fieldtype: "Data" }] }] }],
  },
  {
    name: "items",
    label: "Items",
    sections: [
      {
        columns: [
          {
            fields: [
              { fieldname: "items", fieldtype: "Table", options: "Deal Item" },
              { fieldname: "secret", fieldtype: "Data", hidden: true },
            ],
          },
        ],
      },
    ],
  },
  {
    name: "notes",
    label: "Notes",
    sections: [{ columns: [{ fields: [{ fieldname: "note", fieldtype: "Data" }] }] }],
  },
];

function mount(errors: Record<string, FieldError>) {
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp(
    defineComponent({
      setup: () => () => h(FormLayout, { layout: LAYOUT, doc: { items: [] } }),
    })
  );
  app.provide(CommitKey, NO_COMMIT);
  app.provide(FieldErrorsKey, ref(errors));
  app.mount(host);
  return host;
}

function dotted(root: HTMLElement) {
  return [...root.querySelectorAll("[data-tab]")]
    .filter((tab) => tab.querySelector(".rounded-full"))
    .map((tab) => tab.getAttribute("data-tab"));
}

describe("the tab strip's error dot", () => {
  it("marks each tab that holds a marked field, a row cell counting for its table", () => {
    const root = mount({
      customer: "Customer is required",
      [JSON.stringify(["items", "name:r1", "item"])]: "Item is required",
    });

    expect(dotted(root)).toEqual(["details", "items"]);
  });

  it("leaves a tab whose only marked field is hidden", () => {
    const root = mount({ secret: "Secret is required" });

    expect(dotted(root)).toEqual([]);
  });
});
