// A Duration filter reads a typed number in the field's smallest unit, as the form does.
import { afterEach, describe, expect, it } from "vitest";
import { createApp, h, nextTick, ref } from "vue";
import type { App } from "vue";
import { getFilterableFields } from "../../Filter/getFilterableFields";
import { valueControl } from "../../Filter/valueControl";
import type { Filter } from "../../Filter/types";
import type { RawMetaField } from "../../FormLayout/types";
import DurationField from "../../Fields/DurationField.vue";
import QuickFilterInputs from "../QuickFilterInputs.vue";

const SPENT: RawMetaField = {
  fieldname: "spent",
  fieldtype: "Duration",
  label: "Spent",
  hide_days: 1,
  hide_seconds: 1,
};

let app: App | undefined;
let host: HTMLElement | undefined;

afterEach(() => {
  app?.unmount();
  host?.remove();
  app = undefined;
  host = undefined;
});

function mount(render: () => ReturnType<typeof h>) {
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({ render });
  app.mount(host);
  return host.querySelector("input") as HTMLInputElement;
}

async function type(input: HTMLInputElement, text: string) {
  input.dispatchEvent(new Event("focus"));
  input.value = text;
  input.dispatchEvent(new Event("input"));
  input.dispatchEvent(new Event("blur"));
  await nextTick();
}

const spent = () => getFilterableFields([SPENT], "Task").find((f) => f.fieldname === "spent")!;

describe("a Duration filter with hide_days and hide_seconds", () => {
  it("reads a typed 90 as minutes in the filter popover", async () => {
    const committed: unknown[] = [];
    const { props } = valueControl({ fieldname: "spent", operator: "equals", value: "", field: spent() });
    const input = mount(() =>
      h(DurationField, { ...props, onChange: (v: unknown) => committed.push(v) } as any),
    );
    await type(input, "90");
    expect(committed).toEqual([5400]);
  });

  it("reads a typed 90 as minutes in the quick filter", async () => {
    const filters = ref<Filter[]>([]);
    const input = mount(() =>
      h(QuickFilterInputs, {
        fields: [spent()],
        filters: filters.value,
        "onUpdate:filters": (v: Filter[]) => (filters.value = v),
      }),
    );
    await type(input, "90");
    expect(filters.value.map((f) => f.value)).toEqual([5400]);
  });
});
