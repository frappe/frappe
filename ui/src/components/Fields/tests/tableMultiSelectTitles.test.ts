// What a saved Table MultiSelect chip shows: the search's label, else the title the host holds
// for it under `LinkTitlesKey`, keyed by the Link column's doctype, else its name. Fetch is faked.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, ref } from "vue";
import type { App } from "vue";
import TableMultiSelectField from "../TableMultiSelectField.vue";
import { LinkTitlesKey } from "../types";
import type { FieldMeta } from "../types";

let app: App | undefined;
let host: HTMLElement | undefined;
let found: { value: string; label?: string }[];

beforeEach(() => {
  found = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify({ data: found }), { status: 200 }))
  );
});

afterEach(() => {
  app?.unmount();
  host?.remove();
  app = undefined;
  host = undefined;
  vi.unstubAllGlobals();
});

const field: FieldMeta = {
  fieldname: "customers",
  fieldtype: "Table MultiSelect",
  label: "Customers",
  options: "Customer Item",
  childFields: [{ fieldname: "customer", fieldtype: "Link", label: "Customer", options: "Customer" }],
};

async function render(names: string[], titles: Record<string, string>) {
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({
    render: () =>
      h(TableMultiSelectField, { field, modelValue: names.map((customer) => ({ customer })) }),
  });
  app.provide(LinkTitlesKey, ref(titles));
  app.mount(host);
  for (let tick = 0; tick < 5; tick++) await nextTick();
  await new Promise((resolve) => setTimeout(resolve));
  return host;
}

function chips(root: HTMLElement) {
  return [...root.querySelectorAll("button span.h-7")].map((chip) => chip.textContent!.trim());
}

describe("a saved Table MultiSelect chip", () => {
  it("shows the title the host holds for it under the Link column's doctype", async () => {
    const root = await render(["CUST-001", "CUST-002", "CUST-003"], {
      "Customer::CUST-001": "Acme Corp",
      "Supplier::CUST-002": "Not this one",
    });

    expect(chips(root)).toEqual(["Acme Corp", "CUST-002", "CUST-003"]);
  });

  it("shows the search's label when the search returns it", async () => {
    found = [{ value: "CUST-001", label: "Acme (searched)" }];
    const root = await render(["CUST-001"], { "Customer::CUST-001": "Acme Corp" });

    expect(chips(root)).toEqual(["Acme (searched)"]);
  });
});
