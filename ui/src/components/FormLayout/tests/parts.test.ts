// A part in the DOM: a cell beside its field with a field-style label, and a
// section of its own with the section's heading, bare without a label.
import { afterEach, describe, expect, it } from "vitest";
import { createApp, defineComponent, h } from "vue";
import type { App } from "vue";
import FormLayoutColumn from "../FormLayoutColumn.vue";
import FormLayoutSection from "../FormLayoutSection.vue";
import { DocKey, HasTabsKey, ResolveFieldKey, UpdateKey } from "../types";
import type { Column, Section } from "../types";

const StubField = defineComponent({
  props: { field: { type: Object, required: true }, modelValue: null },
  setup: (props) => () => h("input", { "data-stub": props.field.fieldname }),
});

const Badge = defineComponent({
  props: { text: { type: String, default: "" } },
  setup: (props) => () => h("span", { "data-badge": "" }, props.text),
});

let app: App | undefined;
let host: HTMLElement | undefined;

afterEach(() => {
  app?.unmount();
  host?.remove();
});

function mount(node: any) {
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({ render: () => node });
  app.provide(DocKey, { value: {} } as any);
  app.provide(UpdateKey, () => {});
  app.provide(ResolveFieldKey, () => StubField);
  app.provide(HasTabsKey, { value: false } as any);
  app.mount(host);
  return host;
}

const field = (fieldname: string, hidden = false) => ({ fieldname, fieldtype: "Data", hidden }) as any;

const order = (host: HTMLElement) =>
  [...host.querySelectorAll("[data-stub], [data-part]")].map(
    (el) => el.getAttribute("data-stub") ?? `part:${el.getAttribute("data-part")}`
  );

describe("a part in a column", () => {
  it("sits before or after its field, and unanchored ones follow", () => {
    const column: Column = {
      fields: [field("title"), field("status")],
      parts: [
        { name: "after_title", component: Badge, after: "title" },
        { name: "before_title", component: Badge, before: "title" },
        { name: "loose", component: Badge },
      ],
    };
    const host = mount(h(FormLayoutColumn, { column }));
    expect(order(host)).toEqual(["part:before_title", "title", "part:after_title", "status", "part:loose"]);
  });

  it("lands a later part nearer the neighbour, and a part beside a part", () => {
    const column: Column = {
      fields: [field("title")],
      parts: [
        { name: "first", component: Badge, after: "title" },
        { name: "second", component: Badge, after: "title" },
        { name: "beside", component: Badge, after: "first" },
      ],
    };
    expect(order(mount(h(FormLayoutColumn, { column })))).toEqual(["title", "part:second", "part:first", "part:beside"]);
  });

  it("appends parts that anchor only on each other", () => {
    const column: Column = {
      fields: [field("title")],
      parts: [
        { name: "a", component: Badge, after: "b" },
        { name: "b", component: Badge, after: "a" },
      ],
    };
    expect(order(mount(h(FormLayoutColumn, { column })))).toEqual(["title", "part:a", "part:b"]);
  });

  it("keeps its place beside a hidden field", () => {
    const column: Column = {
      fields: [field("title", true), field("status")],
      parts: [{ name: "score", component: Badge, after: "title" }],
    };
    expect(order(mount(h(FormLayoutColumn, { column })))).toEqual(["part:score", "status"]);
  });

  it("draws a field-style label above the component, or nothing", () => {
    const column: Column = {
      fields: [field("title")],
      parts: [
        { name: "labelled", label: "Score", component: Badge, props: { text: "9" }, after: "title" },
        { name: "bare", component: Badge, props: { text: "bare" }, after: "title" },
      ],
    };
    const host = mount(h(FormLayoutColumn, { column }));
    const labelled = host.querySelector('[data-part="labelled"]')!;
    expect(labelled.querySelector("label")?.textContent?.trim()).toBe("Score");
    expect(labelled.querySelector("[data-badge]")?.textContent).toBe("9");
    expect(host.querySelector('[data-part="bare"] label')).toBeNull();
  });
});

describe("a part as a section", () => {
  it("draws the section heading and the component instead of columns", () => {
    const section: Section = {
      name: "chart",
      label: "Pipeline",
      columns: [],
      part: { name: "chart", component: Badge, props: { text: "chart" } },
    };
    const host = mount(h(FormLayoutSection, { section }));
    expect(host.querySelector(".section-header")?.textContent?.trim()).toBe("Pipeline");
    expect(host.querySelector('.section-body [data-part="chart"] [data-badge]')?.textContent).toBe("chart");
    expect(host.querySelector(".column")).toBeNull();
  });

  it("without a label is a bare block", () => {
    const section: Section = { name: "note", columns: [], part: { name: "note", component: Badge } };
    const host = mount(h(FormLayoutSection, { section }));
    expect(host.querySelector(".section-header")).toBeNull();
    expect(host.querySelector('[data-part="note"]')).not.toBeNull();
  });
});
