import { afterEach, describe, expect, it } from "vitest";
import { createApp, h, nextTick } from "vue";
import type { App } from "vue";
import DurationField from "../DurationField.vue";
import type { FieldMeta } from "../types";

// The editable Duration shows the same units as the read-only text: days unless hide_days, seconds unless hide_seconds.

let app: App | undefined;
let host: HTMLElement | undefined;

afterEach(() => {
  app?.unmount();
  host?.remove();
  app = undefined;
  host = undefined;
});

function render(modelValue: number, extra: Partial<FieldMeta> = {}) {
  const committed: unknown[] = [];
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({
    render: () =>
      h(DurationField, {
        field: { fieldname: "spent", fieldtype: "Duration", ...extra },
        modelValue,
        onChange: (value: unknown) => committed.push(value),
      }),
  });
  app.mount(host);
  const input = host.querySelector("input") as HTMLInputElement;
  return { input, committed };
}

describe("DurationField", () => {
  it("shows days and seconds by default", () => {
    expect(render(93784).input.value).toBe("1d 2h 3m 4s");
  });

  it("folds days into hours and rounds the seconds as the field asks", () => {
    expect(render(93784, { hideDays: true, hideSeconds: true }).input.value).toBe("26h 3m");
  });

  it("reads a typed day", async () => {
    const { input, committed } = render(0);
    input.dispatchEvent(new Event("focus"));
    input.value = "1d 2h";
    input.dispatchEvent(new Event("input"));
    input.dispatchEvent(new Event("blur"));
    await nextTick();
    expect(committed).toEqual([93600]);
  });
});
