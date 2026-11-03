import { afterEach, describe, expect, it } from "vitest";
import { createApp, h, nextTick } from "vue";
import type { App, Component } from "vue";
import DateField from "../DateField.vue";
import DatetimeField from "../DatetimeField.vue";
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

function render(component: Component, fieldtype: string, modelValue: string | null) {
  const committed: unknown[] = [];
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({
    render: () =>
      h(component, {
        field: { fieldname: "on", fieldtype },
        modelValue,
        onChange: (value: unknown) => committed.push(value),
      }),
  });
  app.mount(host);
  const input = host.querySelector("input") as HTMLInputElement;
  return { input, committed };
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
});
