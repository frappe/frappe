// The builder's own value cell, exported so a host's `#condition-value` can keep it.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick } from "vue";
import type { App } from "vue";
import { ConditionValueControl } from "..";
import type { ConditionOperator, ConditionValue } from "../types";

let app: App | undefined;
let host: HTMLElement | undefined;

afterEach(() => {
  app?.unmount();
  host?.remove();
});

function mount(operator: ConditionOperator, modelValue: ConditionValue) {
  const onUpdate = vi.fn();
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({
    render: () =>
      h(ConditionValueControl, {
        field: {
          fieldname: "remarks",
          fieldtype: "Data",
          label: "Remarks",
          value: "remarks",
        },
        operator,
        modelValue,
        "onUpdate:modelValue": onUpdate,
      }),
  });
  app.mount(host);
  return { onUpdate, root: host };
}

describe("ConditionValueControl", () => {
  it("edits a text value in a text box", async () => {
    const { onUpdate, root } = mount("equals", "urgent");
    const input = root.querySelector("input")!;
    expect(input.value).toBe("urgent");

    input.value = "late";
    input.dispatchEvent(new Event("input"));
    await nextTick();
    expect(onUpdate).toHaveBeenLastCalledWith("late");
  });

  it("offers Set and Not Set for is", () => {
    const { root } = mount("is", "not set");
    expect(root.querySelector('[role="combobox"]')?.textContent).toContain(
      "Not Set"
    );
  });
});
