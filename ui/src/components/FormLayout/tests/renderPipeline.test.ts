import { afterEach, describe, expect, it } from "vitest";
import { createApp, defineComponent, h } from "vue";
import type { App } from "vue";
import FormLayoutColumn from "../FormLayoutColumn.vue";
import { buildLayoutFromMeta } from "../buildLayoutFromMeta";
import { resolveLayout } from "../resolveLayout";
import { DocKey, ResolveFieldKey, UpdateKey } from "../types";
import type { FieldNode, FieldOverride, RawMetaField } from "../types";

/**
 * The only test in this repo that goes meta → DOM: raw DocFields in, rendered
 * controls out, through the same three steps a real form takes
 * (`buildLayoutFromMeta` → `resolveLayout` → the column/field components).
 *
 * It stops at `FormLayoutColumn` rather than `FormLayout` on purpose — the root
 * pulls in frappe-ui's `Tabs`, which cannot be transformed under this runner,
 * and the tabs/sections are not what the field pipeline decides. Every real
 * field component is stubbed out for the same reason: what is asserted here is
 * *which* fields reach the DOM and what meta they arrive with, not how a
 * `Currency` widget paints itself.
 */

// Renders as `<input data-stub data-fieldname data-read-only data-reqd>` so the
// resolved meta each control was handed is readable straight off the DOM.
const StubField = defineComponent({
  props: { field: { type: Object, required: true }, modelValue: null },
  setup(props) {
    return () =>
      h("input", {
        "data-stub": "",
        "data-fieldname": props.field.fieldname,
        "data-read-only": String(!!props.field.readOnly),
        "data-reqd": String(!!props.field.reqd),
        value: props.modelValue ?? "",
      });
  },
});

let app: App | undefined;
let host: HTMLElement | undefined;

afterEach(() => {
  app?.unmount();
  host?.remove();
  app = undefined;
  host = undefined;
});

/** Build from meta, resolve against `doc`, render the first column. */
function render(
  fields: RawMetaField[],
  doc: Record<string, any> = {},
  overrides: Record<string, FieldOverride> = {}
): HTMLElement {
  let layout = buildLayoutFromMeta(fields);
  // The override carrier is plain schema data, so an app applies it by walking
  // the tree — exactly how `joinLayout` will thread it through.
  for (const tab of layout)
    for (const section of tab.sections)
      for (const column of section.columns)
        column.fields = column.fields.map((f) =>
          overrides[f.fieldname] ? { ...f, override: overrides[f.fieldname] } : f
        );
  layout = resolveLayout(layout, doc);

  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({
    render: () => h(FormLayoutColumn, { column: layout[0].sections[0].columns[0] }),
  });
  app.provide(DocKey, { value: doc } as any);
  app.provide(UpdateKey, (name: string, value: any) => (doc[name] = value));
  app.provide(ResolveFieldKey, () => StubField);
  app.mount(host);
  return host;
}

const rendered = (host: HTMLElement) =>
  [...host.querySelectorAll("[data-stub]")].map((el) =>
    el.getAttribute("data-fieldname")
  );

const field = (over: Partial<RawMetaField> & { fieldname: string }) =>
  ({ fieldtype: "Data", ...over }) as RawMetaField;

describe("meta → DOM", () => {
  it("renders one control per data field, in meta order", () => {
    const host = render([
      field({ fieldname: "item_code" }),
      field({ fieldname: "qty", fieldtype: "Float" }),
      field({ fieldname: "rate", fieldtype: "Currency" }),
    ]);
    expect(rendered(host)).toEqual(["item_code", "qty", "rate"]);
  });

  it("keeps a statically-hidden field out of the DOM", () => {
    const host = render([
      field({ fieldname: "item_code" }),
      field({ fieldname: "secret", hidden: 1 }),
    ]);
    expect(rendered(host)).toEqual(["item_code"]);
  });

  it("hides a field whose depends_on is false against the doc", () => {
    const host = render(
      [
        field({ fieldname: "item_code" }),
        field({ fieldname: "discount", depends_on: "eval:doc.has_discount" }),
      ],
      { has_discount: 0 }
    );
    expect(rendered(host)).toEqual(["item_code"]);
  });

  it("carries resolved reqd and readOnly onto the rendered control", () => {
    const host = render(
      [
        field({
          fieldname: "rate",
          mandatory_depends_on: "eval:doc.billable",
          read_only_depends_on: "eval:doc.locked",
        }),
      ],
      { billable: 1, locked: 1 }
    );
    const el = host.querySelector("[data-stub][data-fieldname='rate']")!;
    expect(el.getAttribute("data-reqd")).toBe("true");
    expect(el.getAttribute("data-read-only")).toBe("true");
  });

  it("an override puts a depends_on-hidden field back in the DOM", () => {
    const host = render(
      [field({ fieldname: "discount", depends_on: "eval:doc.has_discount" })],
      { has_discount: 0 },
      { discount: { hidden: false } }
    );
    expect(rendered(host)).toEqual(["discount"]);
  });

  it("an override takes a field out of the DOM against its depends_on", () => {
    const host = render(
      [field({ fieldname: "discount", depends_on: "eval:doc.has_discount" })],
      { has_discount: 1 },
      { discount: { hidden: true } }
    );
    expect(rendered(host)).toEqual([]);
  });

  it("an override cannot render a permlevel-denied field", () => {
    // The denial arrives the way `withAccess` writes it: the flag plus the
    // `perm_denied` stamp that marks it as a permission decision.
    const host = render(
      [field({ fieldname: "salary", hidden: 1, permlevel: 1, perm_denied: 1 })],
      {},
      { salary: { hidden: false } }
    );
    expect(rendered(host)).toEqual([]);
  });

  it("an override DOES render a meta-hidden field the reader may write", () => {
    // Same permlevel, no denial — the reader has the level, so the only reason
    // it is hidden is the meta, which an override may lift.
    const host = render(
      [field({ fieldname: "salary", hidden: 1, permlevel: 1 })],
      {},
      { salary: { hidden: false } }
    );
    expect(rendered(host)).toEqual(["salary"]);
  });

  it("an override flips reqd and readOnly on the rendered control", () => {
    const host = render(
      [field({ fieldname: "rate", reqd: 1, read_only: 1 })],
      {},
      { rate: { reqd: false, readOnly: false } }
    );
    const el = host.querySelector("[data-stub][data-fieldname='rate']")!;
    expect(el.getAttribute("data-reqd")).toBe("false");
    expect(el.getAttribute("data-read-only")).toBe("false");
  });
});

/** Render one hand-built column (no meta step) so a `ui` overlay is expressible. */
function renderColumn(fields: FieldNode[], doc: Record<string, any> = {}) {
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({
    render: () => h(FormLayoutColumn, { column: { name: "c", fields } }),
  });
  app.provide(DocKey, { value: doc } as any);
  app.provide(UpdateKey, (name: string, value: any) => (doc[name] = value));
  app.provide(ResolveFieldKey, () => StubField);
  app.mount(host);
  return host;
}

describe("the `ui` overlay reaches the DOM", () => {
  it("binds ui.props onto the control", () => {
    const host = renderColumn([
      { fieldname: "rate", fieldtype: "Currency", ui: { props: { placeholder: "0.00" } } },
    ]);
    const el = host.querySelector("[data-stub]")!;
    expect(el.getAttribute("placeholder")).toBe("0.00");
  });

  it("ui.props cannot clobber the field it is decorating", () => {
    // The overlay is presentation. Re-pointing a control at another field
    // through it would silently write the wrong key back into the doc.
    const host = renderColumn([
      {
        fieldname: "rate",
        fieldtype: "Currency",
        ui: { props: { field: { fieldname: "hijacked", fieldtype: "Data" } } },
      },
    ]);
    expect(host.querySelector("[data-stub]")!.getAttribute("data-fieldname")).toBe(
      "rate"
    );
  });

  it("fires a ui.on.click handler — the route that makes a Button live", () => {
    let clicked = 0;
    const host = renderColumn([
      {
        fieldname: "recalculate",
        fieldtype: "Button",
        label: "Recalculate",
        ui: { on: { click: () => clicked++ } },
      },
    ]);
    host.querySelector("[data-stub]")!.dispatchEvent(new Event("click"));
    expect(clicked).toBe(1);
  });
});
