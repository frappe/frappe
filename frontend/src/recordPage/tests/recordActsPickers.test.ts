// A date an act sets must show in the closed picker, even while the field holds focus
// (the Create dialog focuses its first field).
import { afterEach, describe, expect, it } from "vitest";
import { createApp, h, nextTick, reactive } from "vue";
import type { App } from "vue";
import { getFieldComponent, resetFormatDefaults, setFormatDefaults } from "@framework/ui/FormLayout";
import { setValuesEntry } from "../recordActs";

let app: App | undefined;
let host: HTMLElement | undefined;

afterEach(() => {
  app?.unmount();
  host?.remove();
  resetFormatDefaults();
});

const TYPES = { due: "Date", starts: "Datetime", at: "Time" } as const;

function mountForm() {
  const doc = reactive<Record<string, any>>({ due: null, starts: null, at: null });
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({
    render: () =>
      Object.keys(TYPES).map((fieldname) =>
        h(getFieldComponent(TYPES[fieldname as keyof typeof TYPES]), {
          field: { fieldname, fieldtype: TYPES[fieldname as keyof typeof TYPES] },
          modelValue: doc[fieldname],
          onChange: (value: unknown) => (doc[fieldname] = value),
        })
      ),
  });
  app.mount(host);
  const form = {
    doc: () => doc,
    field: (fieldname: string) => ({ fieldtype: TYPES[fieldname as keyof typeof TYPES] }),
    commit: async () => {},
    errors: () => ({}),
  };
  return form;
}

describe("record.set_values on the date pickers", () => {
  it("shows what it set in the closed picker, focused or not", async () => {
    setFormatDefaults({ date_format: "dd-mm-yyyy", time_format: "HH:mm" });
    const form = mountForm();
    (host!.querySelector("input") as HTMLInputElement).focus();

    await setValuesEntry(form).item.run!(null as any, { values: { due: "2026-11-03", starts: "2026-11-04 09:15:00", at: "10:30:00" } });
    for (let turn = 0; turn < 3; turn++) await nextTick();

    const shown = [...host!.querySelectorAll("input")].map((input) => input.value);
    expect(shown).toEqual(["03-11-2026", "04-11-2026 09:15", "10:30"]);
  });
});
