import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick } from "vue";
import type { App } from "vue";
import type { ChoiceOption, ChoiceValue } from "../types";

let app: App | null = null;

const OPTIONS: ChoiceOption[] = [
  { label: "School", value: "School" },
  { label: "Company", value: "Company", icon: "lucide-building" },
];

async function mountStep(modelValue: ChoiceValue | null = null) {
  const { default: ChoiceStep } = await import("../ChoiceStep.vue");
  const selected = vi.fn();
  const deselected = vi.fn();
  const updated = vi.fn();
  const el = document.createElement("div");
  app = createApp({
    render: () =>
      h(ChoiceStep, {
        options: OPTIONS,
        modelValue,
        onSelect: selected,
        onDeselect: deselected,
        "onUpdate:modelValue": updated,
      }),
  });
  app.mount(el);
  return { el, selected, deselected, updated };
}

afterEach(() => {
  app?.unmount();
  app = null;
});

describe("ChoiceStep", () => {
  it("picks a chip and reports the option", async () => {
    const { el, selected, updated } = await mountStep();
    const chips = el.querySelectorAll("button");
    expect(chips).toHaveLength(2);
    expect(el.querySelector(".lucide-building")).not.toBeNull();

    chips[1].click();
    await nextTick();
    expect(selected).toHaveBeenCalledWith(OPTIONS[1]);
    expect(updated).toHaveBeenCalledWith("Company");
  });

  it("marks the chosen chip and clears it when picked again", async () => {
    const { el, deselected, updated } = await mountStep("School");
    const chosen = el.querySelectorAll("button")[0];
    expect(chosen.getAttribute("aria-pressed")).toBe("true");
    expect(chosen.querySelector(".lucide-x")).not.toBeNull();

    chosen.click();
    await nextTick();
    expect(deselected).toHaveBeenCalledWith(OPTIONS[0]);
    expect(updated).toHaveBeenCalledWith(null);
  });
});
