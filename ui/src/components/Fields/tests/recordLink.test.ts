// A Link or Dynamic Link value opens the record it names, through the host's `RecordLinkKey`.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, ref } from "vue";
import type { App, Component } from "vue";
import LinkField from "../LinkField.vue";
import DynamicLinkField from "../DynamicLinkField.vue";
import { DocKey, LinkTitlesKey, RecordLinkKey } from "../types";
import type { FieldMeta, RecordLink } from "../types";

let app: App | undefined;
let host: HTMLElement | undefined;
let opened: [string, string][];

const ROUTED: RecordLink = {
  href: (doctype, name) =>
    doctype === "No Route" ? null : `/desk/${doctype.toLowerCase()}/${name}`,
  open: (doctype, name) => opened.push([doctype, name]),
};

beforeEach(() => {
  opened = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify({ data: [] }), { status: 200 }))
  );
});

afterEach(() => {
  app?.unmount();
  host?.remove();
  app = undefined;
  host = undefined;
  vi.unstubAllGlobals();
});

function render(
  component: Component,
  field: FieldMeta,
  modelValue: string | null,
  options: { recordLink?: RecordLink | null; doc?: Record<string, any> } = {}
) {
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({ render: () => h(component, { field, modelValue }) });
  if (options.recordLink !== undefined) app.provide(RecordLinkKey, options.recordLink);
  app.provide(DocKey, ref(options.doc ?? {}));
  app.provide(LinkTitlesKey, ref({ "Customer::CUST-001": "Acme Corp" }));
  app.mount(host);
  return host;
}

function arrow(root: HTMLElement) {
  return root.querySelector<HTMLAnchorElement>('a[data-slot="redirect"]');
}

function click(anchor: HTMLAnchorElement, init: MouseEventInit = {}) {
  const event = new MouseEvent("click", { bubbles: true, cancelable: true, button: 0, ...init });
  anchor.dispatchEvent(event);
  return event;
}

const customer: FieldMeta = { fieldname: "customer", fieldtype: "Link", label: "Customer", options: "Customer" };

describe("a Link field's arrow", () => {
  it("shows with a value and an address, linking to the record", () => {
    const root = render(LinkField, customer, "CUST-001", { recordLink: ROUTED });

    expect(arrow(root)?.getAttribute("href")).toBe("/desk/customer/CUST-001");
    expect(arrow(root)?.getAttribute("aria-label")).toBe("Open Acme Corp");
  });

  it("does not show with no value", () => {
    const root = render(LinkField, customer, null, { recordLink: ROUTED });

    expect(arrow(root)).toBeNull();
  });

  it("does not show when the doctype has no address", () => {
    const field = { ...customer, options: "No Route" };
    const root = render(LinkField, field, "X-1", { recordLink: ROUTED });

    expect(arrow(root)).toBeNull();
  });

  it.each([
    { host: "a null key", recordLink: null },
    { host: "no key", recordLink: undefined },
  ])("does not show with $host, as in a filter", ({ recordLink }) => {
    const root = render(LinkField, customer, "CUST-001", { recordLink });

    expect(arrow(root)).toBeNull();
  });

  it("opens the record on a plain click", () => {
    const root = render(LinkField, customer, "CUST-001", { recordLink: ROUTED });

    const event = click(arrow(root)!);

    expect(event.defaultPrevented).toBe(true);
    expect(opened).toEqual([["Customer", "CUST-001"]]);
  });

  it.each([
    { click: "a Cmd click", init: { metaKey: true } },
    { click: "a Ctrl click", init: { ctrlKey: true } },
    { click: "a Shift click", init: { shiftKey: true } },
    { click: "a middle click", init: { button: 1 } },
  ])("leaves $click to the browser", ({ init }) => {
    const root = render(LinkField, customer, "CUST-001", { recordLink: ROUTED });

    const event = click(arrow(root)!, init);

    expect(event.defaultPrevented).toBe(false);
    expect(opened).toEqual([]);
  });
});

describe("a read-only Link field", () => {
  const readOnly = { ...customer, readOnly: true };

  it("shows its title as a link to the record, with no input", () => {
    const root = render(LinkField, readOnly, "CUST-001", { recordLink: ROUTED });
    const anchor = root.querySelector<HTMLAnchorElement>('[data-slot="link-value"] a')!;

    expect(root.querySelector("input")).toBeNull();
    expect(anchor.textContent?.trim()).toBe("Acme Corp");
    expect(anchor.getAttribute("href")).toBe("/desk/customer/CUST-001");

    click(anchor);
    expect(opened).toEqual([["Customer", "CUST-001"]]);
  });

  it("shows plain text when the doctype has no address", () => {
    const root = render(LinkField, { ...readOnly, options: "No Route" }, "X-1", {
      recordLink: ROUTED,
    });

    expect(root.querySelector('[data-slot="link-value"] a')).toBeNull();
    expect(root.querySelector('[data-slot="link-value"]')?.textContent?.trim()).toBe("X-1");
  });
});

describe("a Dynamic Link field", () => {
  const reference: FieldMeta = {
    fieldname: "reference_name",
    fieldtype: "Dynamic Link",
    label: "Reference",
    options: "reference_doctype",
  };

  it("links to the record in its sibling field's doctype", async () => {
    const root = render(DynamicLinkField, reference, "SI-001", {
      recordLink: ROUTED,
      doc: { reference_doctype: "Invoice" },
    });
    await nextTick();

    expect(arrow(root)?.getAttribute("href")).toBe("/desk/invoice/SI-001");
    click(arrow(root)!);
    expect(opened).toEqual([["Invoice", "SI-001"]]);
  });

  it("shows no arrow while its sibling field is empty", () => {
    const root = render(DynamicLinkField, reference, "SI-001", { recordLink: ROUTED });

    expect(arrow(root)).toBeNull();
  });

  it("shows a read-only value as a link", () => {
    const root = render(DynamicLinkField, { ...reference, readOnly: true }, "SI-001", {
      recordLink: ROUTED,
      doc: { reference_doctype: "Invoice" },
    });

    expect(root.querySelector('[data-slot="link-value"] a')?.getAttribute("href")).toBe(
      "/desk/invoice/SI-001"
    );
  });
});
