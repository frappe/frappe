// A pointer opens a picker row with its popover open, and the row hands its error to the panel control.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, ref } from "vue";

vi.mock("frappe-ui", async (importOriginal) => ({
  ...((await importOriginal()) as Record<string, unknown>),
  call: vi.fn(),
  toast: { success: vi.fn(), error: vi.fn() },
  createResource: () => ({
    data: null,
    loading: false,
    fetch() {},
    reload() {},
  }),
  frappeRequest: vi.fn(),
}));
vi.mock("@framework/ui/api", () => ({
  runMethod: vi.fn(async () => ({ data: null })),
  getMeta: vi.fn(async () => ({ data: null })),
}));

import {
  CommitKey,
  DocKey,
  NO_COMMIT,
  ResolveFieldKey,
  UpdateKey,
} from "@framework/ui/FormLayout/types";
import type { FieldNode } from "@framework/ui/FormLayout/types";
import { FieldErrorsKey, fieldErrorKey } from "@framework/ui/fields/types";
import PanelField from "../PanelField.vue";

const seen: Record<string, any>[] = [];
const Control = defineComponent({
  inheritAttrs: false,
  setup:
    (_props, { attrs }) =>
    () => (seen.push({ ...attrs }), h("input")),
});

const mounted: ReturnType<typeof createApp>[] = [];

afterEach(() => {
  for (const app of mounted.splice(0)) app.unmount();
  document.body.innerHTML = "";
  seen.length = 0;
});

async function mount(field: FieldNode) {
  const root = document.createElement("div");
  document.body.appendChild(root);
  const app = createApp(
    defineComponent({ render: () => h(PanelField, { field }) })
  );
  app.provide(DocKey, ref({}));
  app.provide(FieldErrorsKey, ref({ [fieldErrorKey("f")]: ["Bad value"] }));
  app.provide(UpdateKey, vi.fn());
  app.provide(CommitKey, NO_COMMIT);
  app.provide(ResolveFieldKey, () => Control);
  app.mount(root);
  mounted.push(app);
  await nextTick();
  return root;
}

describe.each([
  "Link",
  "Dynamic Link",
  "Select",
  "Autocomplete",
  "Date",
  "Datetime",
  "Time",
])("a %s row", (fieldtype) => {
  const field: FieldNode = {
    fieldname: "f",
    fieldtype,
    label: "Pick",
    options: "Role",
  };

  it("opens its control with the popover open when a pointer opens the row", async () => {
    const root = await mount(field);
    root.querySelector<HTMLElement>('[data-fieldname="f"]')!.click();
    await nextTick();
    expect(seen.at(-1)).toMatchObject({ panel: true, openPicker: true });
  });

  it("hands its error to the control", async () => {
    const root = await mount(field);
    root.querySelector<HTMLElement>('[data-fieldname="f"]')!.click();
    await nextTick();
    expect(seen.at(-1)?.error).toEqual(["Bad value"]);
  });
});
