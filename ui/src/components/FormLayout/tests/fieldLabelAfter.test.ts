// A host marks a field's label through the `label-after` slot; without it the field draws as before.
import { afterEach, describe, expect, it } from "vitest";
import { createApp, defineComponent, h, nextTick, ref } from "vue";
import type { App, Component } from "vue";
import FormLayoutField from "../FormLayoutField.vue";
import { DocKey, ResolveFieldKey, UpdateKey } from "../types";
import type { FieldNode } from "../types";

let app: App | undefined;
let host: HTMLElement | undefined;

afterEach(() => {
  app?.unmount();
  host?.remove();
});

const field = {
  fieldname: "posting_date",
  fieldtype: "Data",
  label: "Posting Date",
} as FieldNode;
const One = defineComponent({
  props: ["field"],
  setup: (props) => () =>
    h("div", { class: "control" }, [
      h("label", { "data-slot": "label" }, props.field.label),
      h("input"),
    ]),
});

function draw(control: Component, slots?: Record<string, () => unknown>) {
  host = document.createElement("div");
  document.body.append(host);
  app = createApp({
    render: () => h(FormLayoutField, { field }, slots as any),
  });
  app.provide(DocKey as symbol, {});
  app.provide(UpdateKey as symbol, () => {});
  app.provide(ResolveFieldKey as symbol, () => control);
  app.mount(host);
  return host;
}

describe("FormLayoutField label-after slot", () => {
  it("draws the same output as before when the slot is empty", () => {
    // Template comments only exist in a development build.
    expect(draw(One).innerHTML.replace(/<!--[^]*?-->/g, "")).toBe(
      '<div class="field" data-fieldname="posting_date" data-fieldtype="Data"><div class="control"><label data-slot="label">Posting Date</label><input></div></div>'
    );
  });

  it("puts the slot inside the control's label, after its text", async () => {
    const root = draw(One, {
      "label-after": () => h("span", { "data-mark": "" }, "⑂"),
    });
    await nextTick();
    expect(root.querySelector('[data-slot="label"]')!.innerHTML).toBe(
      'Posting Date<span data-mark="">⑂</span>'
    );
  });

  it("follows the label when the control swaps for another", async () => {
    const swapped = ref(false);
    const Swapping = defineComponent({
      setup: () => () =>
        swapped.value
          ? h("section", [h("label", { "data-slot": "label" }, "Other")])
          : h("div", [h("label", { "data-slot": "label" }, "One")]),
    });
    const root = draw(Swapping, { "label-after": () => h("b", "x") });
    await nextTick();
    swapped.value = true;
    await nextTick();
    await new Promise((resolve) => setTimeout(resolve));
    expect(root.querySelector('[data-slot="label"]')!.innerHTML).toBe(
      "Other<b>x</b>"
    );
  });

  it("draws the slot under a control that has no label", async () => {
    const Heading = defineComponent({
      props: ["field"],
      setup: (props) => () => h("h3", props.field.label),
    });
    const root = draw(Heading, { "label-after": () => h("b", "x") });
    await nextTick();
    expect(root.querySelector('[data-slot="label-after"]')!.innerHTML).toBe("<b>x</b>");
  });
});
