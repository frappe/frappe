import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick } from "vue";
import type { App } from "vue";
import FormLayout from "../FormLayout.vue";
import { CommitKey, NO_COMMIT } from "../types";
import type { FormLayoutSchema } from "../types";

// Container labels translate at draw time with the DocType as context; the tree and a
// tab's identity keep the source string. `Tabs` is stubbed: reka-ui paints nothing here.
vi.mock("frappe-ui", async (importOriginal) => ({
  ...((await importOriginal()) as object),
  Tabs: defineComponent({
    props: { tabs: { type: Array, required: true }, modelValue: [String, Number] },
    setup(props, { slots }) {
      return () => {
        const tabs = props.tabs as any[];
        return h("div", [
          ...tabs.map((tab) =>
            h("button", { "data-tab": tab.identity, "data-label": tab.label })
          ),
          slots["tab-panel"]?.({ tab: tabs[0] }),
        ]);
      };
    },
  }),
}));

const CATALOG: Record<string, string> = {
  "Address:Contact": "Adresse",
  "Billing:Contact": "Facturation",
  "Street:Contact": "Rue",
  Notes: "Remarques",
  Details: "Détails",
};

function translateFromCatalog(message: string, _args?: unknown[], context?: string | null) {
  return CATALOG[`${message}:${context}`] ?? CATALOG[message] ?? message;
}

const LAYOUT: FormLayoutSchema = [
  {
    label: "Address",
    sections: [
      {
        label: "Billing",
        columns: [
          { label: "Street", fields: [{ fieldname: "street", fieldtype: "Data" }] },
        ],
      },
      {
        label: "Notes",
        columns: [{ fields: [{ fieldname: "notes", fieldtype: "Data" }] }],
      },
    ],
  },
  { sections: [] },
];

let app: App | undefined;
let host: HTMLElement | undefined;

beforeEach(() => {
  (globalThis as any).__ = translateFromCatalog;
});

afterEach(() => {
  app?.unmount();
  host?.remove();
  delete (globalThis as any).__;
});

async function mount(doctype?: string) {
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp(
    defineComponent({
      setup: () => () => h(FormLayout, { layout: LAYOUT, doc: {}, doctype }),
    })
  );
  app.provide(CommitKey, NO_COMMIT);
  app.mount(host);
  await nextTick();
  const tabs = [...host.querySelectorAll("[data-tab]")];
  return {
    labels: () => tabs.map((el) => el.getAttribute("data-label")),
    identities: () => tabs.map((el) => el.getAttribute("data-tab")),
    sections: () =>
      [...host!.querySelectorAll(".section-header")].map((el) => el.textContent?.trim()),
    columns: () =>
      [...host!.querySelectorAll(".column > div:first-child")].map((el) =>
        el.textContent?.trim()
      ),
  };
}

describe("container labels translate with the DocType as context", () => {
  it("draws the tab, section and column labels from the catalog", async () => {
    const form = await mount("Contact");
    expect(form.labels()).toEqual(["Adresse", "Détails"]);
    expect(form.sections()).toEqual(["Facturation", "Remarques"]);
    expect(form.columns()).toContain("Rue");
  });

  it("falls back to the text without context", async () => {
    const form = await mount("Lead");
    expect(form.labels()).toEqual(["Address", "Détails"]);
    expect(form.sections()).toEqual(["Billing", "Remarques"]);
    expect(form.columns()).toContain("Street");
  });

  it("keeps a tab's identity on the source label", async () => {
    const translated = (await mount("Contact")).identities();
    app?.unmount();
    host?.remove();
    delete (globalThis as any).__;
    const english = (await mount("Contact")).identities();
    expect(translated).toEqual(["address", "tab-2"]);
    expect(translated).toEqual(english);
  });
});
