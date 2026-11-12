// A Geolocation row in the side panel draws what Details draws: the pin, the summary or
// "Set location", × to clear at the right edge. It has no ↗ and no edit state.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, ref } from "vue";
import type { App } from "vue";
import GeolocationField from "../GeolocationField.vue";

const ONE_POINT = JSON.stringify({
  type: "FeatureCollection",
  features: [{ type: "Feature", properties: {}, geometry: { type: "Point", coordinates: [77.5946, 12.9716] } }],
});

let app: App | undefined;
let host: HTMLElement | undefined;

afterEach(() => {
  app?.unmount();
  host?.remove();
  app = undefined;
  host = undefined;
});

function mount(
  value: string | null,
  options: { readOnly?: boolean; panel?: boolean; error?: string } = {}
) {
  const model = ref(value);
  const onInput = vi.fn((next: string | null) => (model.value = next));
  const onChange = vi.fn();
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({
    render: () =>
      h(GeolocationField, {
        field: { fieldname: "place", fieldtype: "Geolocation", label: "Place", readOnly: options.readOnly },
        modelValue: model.value,
        panel: options.panel ?? true,
        error: options.error,
        errorId: options.error ? "place-error" : undefined,
        "onUpdate:modelValue": onInput,
        onChange,
      }),
  });
  app.mount(host);
  return { root: host, model, onInput, onChange };
}

// What the row shows: its screen-reader-only label is left out.
const text = (root: HTMLElement) => {
  const shown = root.cloneNode(true) as HTMLElement;
  shown.querySelectorAll(".sr-only").forEach((label) => label.remove());
  return shown.textContent!.replace(/\s+/g, " ").trim();
};

describe("a Geolocation panel row", () => {
  it("reads \"Set location\" with a pin when empty, and has no clear button or arrow", () => {
    const { root } = mount(null);
    expect(text(root)).toBe("Set location");
    expect(root.querySelector(".lucide-map-pin")).not.toBeNull();
    expect(root.querySelector("[data-slot=clear]")).toBeNull();
    expect(root.querySelector(".lucide-arrow-up-right")).toBeNull();
    expect(root.querySelector("input")).toBeNull();
  });

  it("reads the Details summary when set", () => {
    const { root } = mount(ONE_POINT);
    expect(text(root)).toBe("12.97160°N, 77.59460°E");
  });

  it("clears with the × and commits the empty value", async () => {
    const { root, model, onChange } = mount(ONE_POINT);
    root.querySelector<HTMLButtonElement>("[data-slot=clear]")!.click();
    await nextTick();
    expect(model.value).toBeNull();
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(text(root)).toBe("Set location");
  });

  it("opens the map dialog on a click", async () => {
    const { root } = mount(null);
    root.querySelector<HTMLButtonElement>("[data-slot=control]")!.click();
    await vi.waitFor(() => expect(document.body.querySelector("[role=dialog]")).not.toBeNull());
  });

  it("keeps a read-only row without a ×, and reads a dash when empty", () => {
    expect(text(mount(null, { readOnly: true }).root)).toBe("—");
    expect(mount(ONE_POINT, { readOnly: true }).root.querySelector("[data-slot=clear]")).toBeNull();
  });

  it("is named by its label and then its summary", () => {
    const button = mount(ONE_POINT).root.querySelector("[data-slot=control]")!;
    expect(button.hasAttribute("aria-label")).toBe(false);
    expect(button.textContent!.replace(/\s+/g, " ").trim()).toBe("Place: 12.97160°N, 77.59460°E");
  });

  it("is a focusable button that opens the map dialog from the keyboard", async () => {
    const button = mount(null).root.querySelector<HTMLButtonElement>("[data-slot=control]")!;
    expect(button.tagName).toBe("BUTTON");
    button.focus();
    expect(document.activeElement).toBe(button);
    // A native button turns Enter and Space into a click.
    button.click();
    await vi.waitFor(() => expect(document.body.querySelector("[role=dialog]")).not.toBeNull());
  });

  it("marks the control invalid and points it at the row's error", () => {
    const button = mount(null, { error: "Place is required" }).root.querySelector("[data-slot=control]")!;
    expect(button.getAttribute("aria-invalid")).toBe("true");
    expect(button.getAttribute("aria-describedby")).toBe("place-error");
  });

  it("keeps the labelled input outside a panel", () => {
    const { root } = mount(ONE_POINT, { panel: false });
    expect(root.querySelector("input")).not.toBeNull();
  });
});
