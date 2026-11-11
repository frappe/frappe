import { afterEach, describe, expect, it } from "vitest";
import { createApp, h, nextTick, ref } from "vue";
import type { App } from "vue";
import ColorField from "../ColorField.vue";

/** A panel Color row is one trigger; the picker opens below it and the value saves on close. */

let app: App | undefined;
let host: HTMLElement | undefined;

afterEach(() => {
  app?.unmount();
  host?.remove();
  app = undefined;
  host = undefined;
});

function render(start: string | null, readOnly = false) {
  const doc = ref(start);
  const committed: unknown[] = [];
  const updates: unknown[] = [];
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({
    render: () =>
      h(ColorField, {
        field: {
          fieldname: "color",
          fieldtype: "Color",
          label: "Color",
          placeholder: "Add Color...",
          readOnly,
        },
        panel: true,
        modelValue: doc.value,
        "onUpdate:modelValue": (value: unknown) => {
          updates.push(value);
          doc.value = value as string;
        },
        onChange: (value: unknown) => committed.push(value),
      }),
  });
  app.mount(host);
  const trigger = host.querySelector("button[data-slot=control]") as HTMLButtonElement;
  return { doc, trigger, committed, updates };
}

async function settle() {
  for (let i = 0; i < 5; i++) await nextTick();
  await new Promise((resolve) => setTimeout(resolve, 0));
}

async function open(trigger: HTMLButtonElement) {
  trigger.click();
  await settle();
}

function hexBox() {
  return document.querySelector("input[data-slot=hex]") as HTMLInputElement;
}

async function type(input: HTMLInputElement, text: string) {
  input.value = text;
  input.dispatchEvent(new Event("input"));
  await settle();
  input.dispatchEvent(new Event("change"));
  await settle();
}

describe("a panel Color row", () => {
  it("draws the swatch before the hex and no label, input or error text of its own", async () => {
    const { trigger } = render("#3b82f6");
    expect(host!.querySelector("input")).toBeNull();
    expect(host!.querySelector("label")).toBeNull();
    expect(trigger.textContent).toContain("#3b82f6");
    expect(trigger.firstElementChild?.nextElementSibling?.textContent).toBe("#3b82f6");
  });

  it("reads the field's placeholder when empty", () => {
    const { trigger } = render("");
    expect(trigger.textContent?.trim()).toBe("Add Color...");
  });

  it("opens no picker for a read-only row", async () => {
    const { trigger } = render("#3b82f6", true);
    expect(trigger.disabled).toBe(true);
    await open(trigger);
    expect(document.querySelector("[data-slot=color-area]")).toBeNull();
  });

  it("commits a swatch once and closes", async () => {
    const { doc, trigger, committed } = render("");
    await open(trigger);
    (document.querySelector("button[aria-label='#ce2c2c']") as HTMLButtonElement).click();
    await settle();
    expect(committed).toEqual(["#ce2c2c"]);
    expect(doc.value).toBe("#ce2c2c");
    expect(document.querySelector("[data-slot=color-area]")).toBeNull();
  });

  it("commits a typed hex through the picker's hex box, as #rrggbb", async () => {
    const { doc, trigger, committed } = render("#171717");
    await open(trigger);
    await type(hexBox(), "1F8CAD");
    expect(committed).toEqual(["#1f8cad"]);
    expect(doc.value).toBe("#1f8cad");
  });

  it("puts a bad typed hex back and commits nothing", async () => {
    const { doc, trigger, committed } = render("#171717");
    await open(trigger);
    await type(hexBox(), "#12345");
    expect(committed).toEqual([]);
    expect(doc.value).toBe("#171717");
    expect(hexBox().value).toBe("#171717");
  });

  it("writes a drag to the draft and commits once, when the picker closes", async () => {
    const { doc, trigger, committed, updates } = render("#ffffff");
    await open(trigger);
    const area = document.querySelector("[data-slot=color-area]") as HTMLElement;
    area.getBoundingClientRect = () => ({ left: 0, top: 0, width: 100, height: 100 }) as DOMRect;
    area.dispatchEvent(new MouseEvent("pointerdown", { clientX: 100, clientY: 0, bubbles: true }));
    area.dispatchEvent(new MouseEvent("pointermove", { clientX: 100, clientY: 50 }));
    area.dispatchEvent(new MouseEvent("pointerup", { clientX: 100, clientY: 50 }));
    await settle();
    expect(updates).toEqual(["#ff0000", "#800000"]);
    expect(committed).toEqual([]);
    trigger.click();
    await settle();
    expect(committed).toEqual(["#800000"]);
    expect(doc.value).toBe("#800000");
  });

  it("commits nothing when the picker closes with the color unchanged", async () => {
    const { trigger, committed } = render("#171717");
    await open(trigger);
    trigger.click();
    await settle();
    expect(committed).toEqual([]);
  });

  it("puts the opening color back and commits nothing on Esc", async () => {
    const { doc, trigger, committed } = render("#ffffff");
    await open(trigger);
    const area = document.querySelector("[data-slot=color-area]") as HTMLElement;
    area.getBoundingClientRect = () => ({ left: 0, top: 0, width: 100, height: 100 }) as DOMRect;
    area.dispatchEvent(new MouseEvent("pointerdown", { clientX: 100, clientY: 0, bubbles: true }));
    area.dispatchEvent(new MouseEvent("pointerup", { clientX: 100, clientY: 0 }));
    await settle();
    expect(doc.value).toBe("#ff0000");
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    await settle();
    expect(doc.value).toBe("#ffffff");
    expect(committed).toEqual([]);
  });
});
