import { afterEach, describe, expect, it } from "vitest";
import { createApp, h, nextTick, ref } from "vue";
import type { App } from "vue";
import CheckField from "../CheckField.vue";

let app: App | undefined;
let host: HTMLElement | undefined;

afterEach(() => {
  app?.unmount();
  host?.remove();
  app = undefined;
  host = undefined;
});

function render(start: unknown) {
  const doc = ref(start);
  const committed: unknown[] = [];
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({
    render: () =>
      h(CheckField, {
        field: { fieldname: "enabled", fieldtype: "Check", label: "Enabled" },
        modelValue: doc.value,
        "onUpdate:modelValue": (value: unknown) => (doc.value = value),
        onChange: (value: unknown) => committed.push(value),
      }),
  });
  app.mount(host);
  const input = host.querySelector("input[type=checkbox]") as HTMLInputElement;
  return { doc, input, committed };
}

async function toggle(input: HTMLInputElement) {
  input.click();
  await nextTick();
}

describe("CheckField", () => {
  it("commits 1 and 0, as the server stores a Check", async () => {
    const { input, committed } = render(0);
    await toggle(input);
    await toggle(input);
    expect(committed).toEqual([1, 0]);
  });

  it.each([0, 1])("leaves a saved %i unchanged after a double toggle", async (start) => {
    const { doc, input } = render(start);
    await toggle(input);
    await toggle(input);
    expect(doc.value).toBe(start);
  });
});
