// A read value pins an optional suffix to its right end, and draws no wrapper without one.
import { describe, expect, it } from "vitest";
import { createApp, h } from "vue";
import ReadValue from "../ReadValue.vue";

function render(slots: Record<string, () => unknown>) {
  const host = document.createElement("div");
  createApp({ render: () => h(ReadValue, { text: "123" }, slots) }).mount(host);
  return host;
}

describe("ReadValue suffix", () => {
  it("pins the suffix after the text", () => {
    const root = render({ suffix: () => h("button", { "data-slot": "x" }) });

    expect(root.querySelector('[data-slot="read-value"] > div.ms-auto [data-slot="x"]')).not.toBeNull();
  });

  it("draws no wrapper without a suffix", () => {
    expect(render({}).querySelector('[data-slot="read-value"] > div')).toBeNull();
  });
});
