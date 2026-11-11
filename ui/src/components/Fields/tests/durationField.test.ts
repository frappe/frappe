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

function render(modelValue: number, extra: Partial<FieldMeta> = {}, props: Record<string, unknown> = {}) {
  const committed: unknown[] = [];
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({
    render: () =>
      h(DurationField, {
        field: { fieldname: "spent", fieldtype: "Duration", ...extra },
        modelValue,
        ...props,
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

  it("reads a typed bare number in the smallest unit it shows", async () => {
    const { input, committed } = render(0, { hideSeconds: true });
    input.dispatchEvent(new Event("focus"));
    input.value = "90";
    input.dispatchEvent(new Event("input"));
    input.dispatchEvent(new Event("blur"));
    await nextTick();
    expect(committed).toEqual([5400]);
  });

  it("shows zero in the smallest unit it shows", () => {
    expect(render(0, { hideSeconds: true }).input.value).toBe("0m");
  });

  it("selects its text on focus, but a panel row opens with the caret at the end", async () => {
    const form = render(5400);
    form.input.focus();
    await nextTick();
    expect([form.input.selectionStart, form.input.selectionEnd]).toEqual([0, 6]);
    app?.unmount();
    host?.remove();

    const { input } = render(5400, {}, { panel: true });
    input.focus();
    await nextTick();
    await nextTick();
    expect(input.value).toBe("1h 30m");
    expect([input.selectionStart, input.selectionEnd]).toEqual([6, 6]);
  });
});
