import { afterEach, describe, expect, it } from "vitest";
import { createApp, h, nextTick } from "vue";
import type { App } from "vue";
import NumberField from "../NumberField.vue";

/** An Int or Long Int commits a whole number, as the server stores it. A Long Int past 2^53 keeps every digit while it is a string: typed, or held as one in the doc. */

const BEYOND_SAFE = "9007199254740993";

let app: App | undefined;
let host: HTMLElement | undefined;

afterEach(() => {
  app?.unmount();
  host?.remove();
  app = undefined;
  host = undefined;
});

function render(modelValue: unknown, fieldtype = "Long Int") {
  const live: unknown[] = [];
  const committed: unknown[] = [];
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({
    render: () =>
      h(NumberField, {
        field: { fieldname: "big", fieldtype },
        modelValue,
        "onUpdate:modelValue": (value: unknown) => live.push(value),
        onChange: (value: unknown) => committed.push(value),
      }),
  });
  app.mount(host);
  const input = host.querySelector("input") as HTMLInputElement;
  return { input, live, committed };
}

function type(input: HTMLInputElement, value: string) {
  input.value = value;
  input.dispatchEvent(new Event("input"));
  input.dispatchEvent(new Event("change"));
}

describe("NumberField for Long Int", () => {
  it("shows a stored value past 2^53 digit for digit, without grouping", () => {
    const { input } = render(BEYOND_SAFE);
    expect(input.value).toBe(BEYOND_SAFE);
  });

  it("commits a typed value past 2^53 as a digit string", async () => {
    const { input, live, committed } = render(0);
    type(input, BEYOND_SAFE);
    await nextTick();
    expect(live.at(-1)).toBe(BEYOND_SAFE);
    expect(committed).toEqual([BEYOND_SAFE]);
  });

  it("commits a safe value as a number", async () => {
    const { input, committed } = render(0);
    type(input, "1,234");
    await nextTick();
    expect(committed).toEqual([1234]);
  });
});

describe("NumberField for whole numbers", () => {
  it.each([
    ["Int", "7.6", 7],
    ["Int", "-7.6", -7],
    ["Int", "1,234.9", 1234],
    ["Long Int", "7.6", 7],
  ])("%s commits %s as %s", async (fieldtype, typed, expected) => {
    const { input, live, committed } = render(0, fieldtype);
    type(input, typed);
    await nextTick();
    expect(live.at(-1)).toBe(expected);
    expect(committed).toEqual([expected]);
  });

  it("keeps the fraction of a Float", async () => {
    const { input, committed } = render(0, "Float");
    type(input, "7.6");
    await nextTick();
    expect(committed).toEqual([7.6]);
  });
});
