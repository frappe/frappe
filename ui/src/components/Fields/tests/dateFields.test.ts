import { afterEach, describe, expect, it } from "vitest";
import { createApp, h, nextTick, ref } from "vue";
import type { App, Component } from "vue";
import DateField from "../DateField.vue";
import DatetimeField from "../DatetimeField.vue";
import TimeField from "../TimeField.vue";
import { resetFormatDefaults, setFormatDefaults } from "../../FormLayout/formatDefaults";

// The date pickers read typed text in the user's format, and a blur with no edit commits nothing.

let app: App | undefined;
let host: HTMLElement | undefined;

afterEach(() => {
  app?.unmount();
  host?.remove();
  app = undefined;
  host = undefined;
  resetFormatDefaults();
});

function render(component: Component, fieldtype: string, initial: string | null) {
  const committed: unknown[] = [];
  const modelValue = ref(initial);
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({
    render: () =>
      h(component, {
        field: { fieldname: "on", fieldtype },
        modelValue: modelValue.value,
        onChange: (value: unknown) => committed.push(value),
      }),
  });
  app.mount(host);
  const input = host.querySelector("input") as HTMLInputElement;
  return { input, committed, modelValue };
}

describe("the date pickers", () => {
  it("read a typed date day first in a dd-mm-yyyy format", async () => {
    setFormatDefaults({ date_format: "dd-mm-yyyy" });
    const { input, committed } = render(DateField, "Date", null);
    input.dispatchEvent(new Event("focus"));
    input.value = "3-11-2026";
    input.dispatchEvent(new Event("input"));
    input.dispatchEvent(new Event("blur"));
    await nextTick();
    expect(committed).toEqual(["2026-11-03"]);
  });

  it("commit nothing on a blur with no edit, though the format drops the seconds", async () => {
    setFormatDefaults({ date_format: "dd-mm-yyyy", time_format: "HH:mm" });
    const { input, committed } = render(DatetimeField, "Datetime", "2026-10-24 09:15:30");
    await nextTick();
    expect(input.value).toBe("24-10-2026 09:15");
    input.dispatchEvent(new Event("focus"));
    input.dispatchEvent(new Event("blur"));
    await nextTick();
    expect(committed).toEqual([]);
  });

  // An act sets the doc, not the input: the closed text must follow, focused or not.
  it.each([
    ["Date", DateField, "2026-11-03", "03-11-2026"],
    ["Datetime", DatetimeField, "2026-11-03 09:15:30", "03-11-2026 09:15"],
    ["Time", TimeField, "09:15:30", "09:15"],
  ])("show a %s that is set from outside", async (fieldtype, component, value, text) => {
    setFormatDefaults({ date_format: "dd-mm-yyyy", time_format: "HH:mm" });
    for (const focused of [false, true]) {
      const { input, modelValue } = render(component, fieldtype, null);
      if (focused) input.focus();
      modelValue.value = value;
      await nextTick();
      await nextTick();
      const shown = (host!.querySelector("input") as HTMLInputElement).value;
      expect(shown, `${fieldtype}, focused: ${focused}`).toBe(text);
      app?.unmount();
      host?.remove();
    }
  });

  it("keep the same input when the user types a date", async () => {
    const { input, modelValue } = render(DateField, "Date", null);
    input.dispatchEvent(new Event("focus"));
    input.value = "2026-11-03";
    input.dispatchEvent(new Event("input"));
    input.dispatchEvent(new Event("blur"));
    modelValue.value = "2026-11-03";
    await nextTick();
    await nextTick();
    expect(host!.querySelector("input")).toBe(input);
  });

  it("give focus back to a field that held it when an act sets the date", async () => {
    const { input, modelValue } = render(DateField, "Date", null);
    input.focus();
    modelValue.value = "2026-11-03";
    await nextTick();
    await nextTick();
    await nextTick();
    expect(document.activeElement).toBe(host!.querySelector("input"));
  });

  it("clear a loaded date that an act empties while the field holds focus", async () => {
    setFormatDefaults({ date_format: "dd-mm-yyyy" });
    const { input, modelValue } = render(DateField, "Date", "2026-11-03");
    input.focus();
    modelValue.value = null;
    await nextTick();
    await nextTick();
    expect((host!.querySelector("input") as HTMLInputElement).value).toBe("");
  });

  it("keep the input of a field that does not hold focus when its date changes", async () => {
    const { input, modelValue } = render(DateField, "Date", "2026-11-03");
    modelValue.value = "2026-11-04";
    await nextTick();
    await nextTick();
    expect(host!.querySelector("input")).toBe(input);
    expect(input.value).not.toBe("");
  });

  it("give focus back to a Datetime that held it", async () => {
    const { input, modelValue } = render(DatetimeField, "Datetime", null);
    input.focus();
    modelValue.value = "2026-11-03 09:15:00";
    await nextTick();
    await nextTick();
    await nextTick();
    expect(document.activeElement).toBe(host!.querySelector("input"));
  });
});
