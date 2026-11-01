// The dialog a save opens for the mandatory fields the layout does not show.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, ref } from "vue";

vi.mock("frappe-ui", () => ({
  Button: defineComponent({
    props: { label: String },
    setup(props, { attrs }) {
      return () => h("button", attrs, props.label);
    },
  }),
  call: vi.fn(),
  frappeRequest: vi.fn(),
  toast: { success: vi.fn(), error: vi.fn() },
}));

const roles = ref<string[]>([]);
const writable = ref(false);
vi.mock("@framework/ui/useUserRoles", () => ({ useUserRoles: () => ({ roles }) }));
vi.mock("@framework/ui/useDocPermissions", () => ({
  useDocPermissions: vi.fn(() => ({ holds: () => writable.value })),
}));
vi.mock("@framework/ui/FormLayout", async (importOriginal) => ({
  ...((await importOriginal()) as object),
  // The real FormLayout is exercised in Chrome; an input per field that edits the doc is enough here.
  FormLayout: defineComponent({
    props: { layout: { type: Array, required: true }, doc: { type: Object, required: true } },
    emits: ["update:doc"],
    setup(props, { emit }) {
      const fields = () =>
        (props.layout as any[]).flatMap((tab) =>
          tab.sections.flatMap((section: any) => section.columns.flatMap((column: any) => column.fields)),
        );
      return () =>
        h(
          "form",
          fields().map((field: any) =>
            h("input", {
              name: field.fieldname,
              onInput: (event: Event) =>
                emit("update:doc", { ...props.doc, [field.fieldname]: (event.target as HTMLInputElement).value }),
            }),
          ),
        );
    },
  }),
}));

import { useDocPermissions } from "@framework/ui/useDocPermissions";
import { fieldsToLayout } from "@framework/ui/FormLayout";
import RequiredFieldsDialog from "../dialogs/RequiredFieldsDialog.vue";

const layout = fieldsToLayout([{ fieldname: "batch", fieldtype: "Data", label: "Batch", reqd: true }]);

function render(close = vi.fn()) {
  const root = document.createElement("div");
  document.body.appendChild(root);
  createApp(RequiredFieldsDialog, { layout, doc: { name: "D-1" }, doctype: "Deal", close }).mount(root);
  return { root, close };
}

const button = (root: HTMLElement, label: string) =>
  [...root.querySelectorAll("button")].find((one) => one.textContent?.trim() === label)!;

async function settle() {
  await nextTick();
  await Promise.resolve();
  await nextTick();
}

beforeEach(() => {
  document.body.innerHTML = "";
  roles.value = [];
  writable.value = false;
});

describe("the required-fields dialog", () => {
  it("tells everyone the fields are not on the form, and names the Customize Form check", () => {
    const { root } = render();

    expect(root.textContent).toContain("These fields are required but are not on this form.");
    expect(useDocPermissions).toHaveBeenCalledWith("Customize Form");
  });

  it("adds the layout note only for a System Manager who can write Customize Form", async () => {
    roles.value = ["System Manager"];
    const { root } = render();
    expect(root.querySelector("[data-customize-note]")).toBeNull();

    writable.value = true;
    await settle();
    expect(root.querySelector("[data-customize-note]")?.textContent).toContain("Add them to the Details layout");
  });

  it("does not add the note for a person with write but no System Manager role", async () => {
    writable.value = true;
    const { root } = render();
    await settle();
    expect(root.querySelector("[data-customize-note]")).toBeNull();
  });

  it("keeps the dialog open while a field is empty, and sends the values once filled", async () => {
    const { root, close } = render();

    button(root, "Continue").dispatchEvent(new MouseEvent("click"));
    await settle();
    expect(close).not.toHaveBeenCalled();

    const input = root.querySelector("input")!;
    input.value = "B1";
    input.dispatchEvent(new Event("input"));
    await settle();
    button(root, "Continue").dispatchEvent(new MouseEvent("click"));
    await settle();

    expect(close).toHaveBeenCalledWith(expect.objectContaining({ batch: "B1" }));
  });

  it("closes with nothing on Cancel", async () => {
    const { root, close } = render();

    button(root, "Cancel").dispatchEvent(new MouseEvent("click"));

    expect(close).toHaveBeenCalledWith();
  });
});
