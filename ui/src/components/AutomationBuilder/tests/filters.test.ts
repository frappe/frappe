// @vitest-environment happy-dom
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, ref } from "vue";

vi.mock("frappe-ui", () => ({
  Button: { render: () => h("button") },
  Dropdown: { render: () => h("div") },
  Tooltip: { render: () => h("span") },
}));
vi.mock("../../../composables/useDoctypeMeta", () => ({
  useDoctypeMeta: () => ({
    meta: ref({ fields: [{ fieldname: "enabled", fieldtype: "Check" }] }),
  }),
}));
vi.mock("../../ConditionBuilder", async () => {
  const adapters = await import("../../ConditionBuilder/adapters");
  return {
    ...adapters,
    ConditionBuilder: defineComponent({
      props: ["modelValue"],
      emits: ["update:modelValue"],
      setup:
        (props, { emit }) =>
        () =>
          h(
            "button",
            {
              onClick: () =>
                emit("update:modelValue", {
                  ...props.modelValue,
                  conditions: [
                    { fieldname: "enabled", operator: "equals", value: "No" },
                    { fieldname: "", operator: "equals", value: "" },
                  ],
                }),
            },
            String(props.modelValue.conditions.length)
          ),
    }),
  };
});
import Filters from "../AutomationFilters.vue";

const cleanup = [];
afterEach(() => cleanup.splice(0).forEach((stop) => stop()));

function mountFilters() {
  const value = ref(JSON.stringify([["enabled", "=", 1]]));
  const element = document.createElement("div");
  document.body.append(element);
  const app = createApp(
    defineComponent({
      setup: () => () =>
        h(Filters, {
          doctype: "ToDo",
          modelValue: value.value,
          "onUpdate:modelValue": (next) => {
            value.value = next;
          },
        }),
    })
  );
  app.mount(element);
  cleanup.push(() => {
    app.unmount();
    element.remove();
  });
  return { value, element };
}

describe("filter update echoes", () => {
  it("keeps an unfinished row when a Check edit echoes its numeric stored value", async () => {
    const { value, element } = mountFilters();
    element.querySelector("button").click();
    await nextTick();
    expect(JSON.parse(value.value)).toEqual([["enabled", "=", 0]]);
    expect(element.querySelector("button").textContent).toBe("2");
  });
});
