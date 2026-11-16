import { afterEach, describe, expect, it } from "vitest";
import { createApp, h, nextTick, reactive, ref } from "vue";
import type { App } from "vue";
import ColorField from "../ColorField.vue";
import { focusCell } from "../../Grid/cellNavigation";

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
  const state = reactive({ readOnly, label: "Color" as string | undefined, error: "" });
  const committed: unknown[] = [];
  const updates: unknown[] = [];
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({
    render: () =>
      h(ColorField, {
        field: { fieldname: "color", fieldtype: "Color", label: state.label, readOnly: state.readOnly },
        modelValue: doc.value,
        error: state.error,
        "onUpdate:modelValue": (value: unknown) => {
          updates.push(value);
          doc.value = value as string;
        },
        onChange: (value: unknown) => committed.push(value),
      }),
  });
  app.mount(host);
  const input = host.querySelector("input[data-slot=control]") as HTMLInputElement;
  return { doc, input, committed, state, updates };
}

async function settle() {
  for (let i = 0; i < 5; i++) await nextTick();
  await new Promise((resolve) => setTimeout(resolve, 0));
}

async function openPicker() {
  await settle();
  (host!.querySelector("button[aria-label='Pick a color']") as HTMLButtonElement).click();
  await settle();
}

async function typeOnly(input: HTMLInputElement, text: string) {
  input.value = text;
  input.dispatchEvent(new Event("input"));
  await settle();
}

async function type(input: HTMLInputElement, text: string) {
  await typeOnly(input, text);
  input.dispatchEvent(new Event("change"));
  await settle();
}

describe("ColorField", () => {
  it("commits a swatch's hex once", async () => {
    const { doc, committed } = render("");
    await openPicker();
    const swatch = document.querySelector("button[aria-label='#ce2c2c']") as HTMLButtonElement;
    swatch.click();
    await settle();
    expect(committed).toEqual(["#ce2c2c"]);
    expect(doc.value).toBe("#ce2c2c");
  });

  it("commits a typed hex on change, as #rrggbb", async () => {
    const { doc, input, committed } = render("#171717");
    await type(input, "1F8CAD");
    expect(committed).toEqual(["#1f8cad"]);
    expect(doc.value).toBe("#1f8cad");
  });

  it("puts a valid typed hex on the record before blur, so Ctrl+S saves it", async () => {
    const { doc, input } = render("#171717");
    await typeOnly(input, "#1f8cad");
    expect(doc.value).toBe("#1f8cad");
    await typeOnly(input, "#1f8ca");
    expect(doc.value).toBe("#171717");
    expect(input.value).toBe("#1f8ca");
  });

  it("normalizes the box when the typed hex is the stored color in another case", async () => {
    const { doc, input, committed, updates } = render("#1f8cad");
    await type(input, "1F8CAD");
    expect(input.value).toBe("#1f8cad");
    expect(committed).toEqual([]);
    expect(updates).toEqual([]);
    expect(doc.value).toBe("#1f8cad");
  });

  it("leaves a stored uppercase hex alone when the same color is retyped", async () => {
    const { doc, input, committed, updates } = render("#CE2C2C");
    await type(input, "#ce2c2c");
    expect(committed).toEqual([]);
    expect(updates).toEqual([]);
    expect(doc.value).toBe("#CE2C2C");
  });

  it("takes grid focus in the hex box, not the swatch button", async () => {
    const { input } = render("#171717");
    await settle();
    expect(host!.querySelector("button[data-slot=swatch]")).not.toBeNull();
    host!.className = "grid-cell";
    const row = document.createElement("div");
    row.className = "grid-row";
    host!.replaceWith(row);
    row.appendChild(host!);
    expect(focusCell(row.parentElement!, { rowIndex: 0, columnIndex: 0 })).toBe(true);
    expect(document.activeElement).toBe(input);
    row.remove();
  });

  it("reverts a bad hex to the hex saved with Ctrl+S mid-edit", async () => {
    const { doc, input } = render("#171717");
    await typeOnly(input, "#1f8cad");
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "s", ctrlKey: true }));
    await type(input, "#1f8cadx");
    expect(doc.value).toBe("#1f8cad");
    expect(input.value).toBe("#1f8cad");
  });

  it("reverts a bad hex to a value set from outside while typing", async () => {
    const { doc, input } = render("#171717");
    await typeOnly(input, "#1f8");
    doc.value = "#268c5c";
    await settle();
    await type(input, "#zz");
    expect(doc.value).toBe("#268c5c");
    expect(input.value).toBe("#268c5c");
  });

  it("takes a value set from outside while typing as the start of the edit", async () => {
    const { doc, input, committed } = render("#171717");
    await typeOnly(input, "#1f8");
    doc.value = "#268c5c";
    await settle();
    await type(input, "#268c5c");
    expect(committed).toEqual([]);
  });

  it("ends the edit and shows the stored value when the field turns read-only", async () => {
    const { doc, input, state } = render("#171717");
    await typeOnly(input, "#1f8");
    state.readOnly = true;
    await settle();
    doc.value = "#268c5c";
    await settle();
    expect(input.value).toBe("#268c5c");
  });

  it("decides change against the value when typing began, even after Ctrl+S", async () => {
    const { input, committed } = render("#171717");
    await typeOnly(input, "#00ff00");
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "s", ctrlKey: true }));
    input.dispatchEvent(new Event("change"));
    await settle();
    expect(committed).toEqual(["#00ff00"]);
  });

  it("waits for change before applying #rgb, so retyping a stored hex does not flip it", async () => {
    const { doc, input, committed, updates } = render("#1f8cad");
    await typeOnly(input, "#1f8");
    expect(updates).toEqual([]);
    expect(doc.value).toBe("#1f8cad");
    await type(input, "#abc");
    expect(committed).toEqual(["#aabbcc"]);
    expect(doc.value).toBe("#aabbcc");
  });

  it("keeps a working swatch when an error rebuilds the input row", async () => {
    const { state } = render("#171717");
    state.label = undefined;
    for (const error of ["Required", ""]) {
      state.error = error;
      await settle();
      const input = host!.querySelector("input[data-slot=control]")!;
      const swatches = host!.querySelectorAll("button[data-slot=swatch]");
      expect(swatches).toHaveLength(1);
      expect(swatches[0].parentElement?.parentElement).toBe(input.parentElement);
    }
    await openPicker();
    expect(document.querySelector("[data-slot=color-picker]")).not.toBeNull();
  });

  it("drops the picker while read-only and brings it back after", async () => {
    const { state } = render("#171717");
    await settle();
    state.readOnly = true;
    await settle();
    expect(host!.querySelector("button")).toBeNull();
    state.readOnly = false;
    await settle();
    expect(host!.querySelectorAll("button[data-slot=swatch]")).toHaveLength(1);
  });

  it("puts the hex box before the swatch, so Tab and autofocus reach it first", async () => {
    const { input } = render("#171717");
    await settle();
    const focusable = host!.querySelectorAll("input:not([disabled]), button:not([disabled])");
    expect(focusable[0]).toBe(input);
    expect(focusable[1]?.getAttribute("aria-label")).toBe("Pick a color");
  });

  it("does not commit a bad hex, and shows the stored value again", async () => {
    const { doc, input, committed } = render("#171717");
    await type(input, "#12345");
    expect(committed).toEqual([]);
    expect(doc.value).toBe("#171717");
    expect(input.value).toBe("#171717");
  });

  it("commits the browser color dialog's value", async () => {
    const { committed } = render(null);
    await openPicker();
    const dialog = document.querySelector("input[type=color]") as HTMLInputElement;
    dialog.value = "#123456";
    dialog.dispatchEvent(new Event("change"));
    await settle();
    expect(committed).toEqual(["#123456"]);
  });

  it("commits an emptied box as a cleared value", async () => {
    const { input, committed } = render("#171717");
    await type(input, "");
    expect(committed).toEqual([""]);
  });

  it("shows the swatch and hex with no picker when read-only", async () => {
    const { input } = render("#268c5c", true);
    expect(input.value).toBe("#268c5c");
    expect(input.disabled).toBe(true);
    expect(host!.querySelector("button")).toBeNull();
    const swatch = host!.querySelector("[data-slot=swatch]") as HTMLElement;
    expect(swatch.style.backgroundColor).toBeTruthy();
  });
});
