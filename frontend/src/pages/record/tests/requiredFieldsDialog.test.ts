// The dialog a save opens for the mandatory fields the layout does not show.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";

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

import { fieldsToLayout } from "@framework/ui/FormLayout";
import RequiredFieldsDialog from "../dialogs/RequiredFieldsDialog.vue";

const layout = fieldsToLayout([{ fieldname: "batch", fieldtype: "Data", label: "Batch", reqd: true }]);

const blank = { render: () => null };
const EDITOR = { name: "doctype-editor", params: { name: "Deal" }, query: { layout: "details", row: "FL-7" } };

function render(close = vi.fn(), submitting = false, editRoute?: typeof EDITOR) {
  const root = document.createElement("div");
  document.body.appendChild(root);
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: "/doctype/:name", name: "doctype-editor", component: blank }, { path: "/", component: blank }],
  });
  const push = vi.spyOn(router, "push").mockResolvedValue(undefined);
  const app = createApp(RequiredFieldsDialog, { layout, doc: { name: "D-1" }, doctype: "Deal", close, submitting, editRoute });
  app.use(router);
  app.mount(root);
  return { root, close, push };
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
});

describe("the required-fields dialog", () => {
  it("tells everyone the fields are not on the form, and the layout note and link only with the editor's route", () => {
    const { root } = render();

    expect(root.textContent).toContain("These fields are required but are not on this form.");
    expect(root.querySelector("[data-customize-note]")).toBeNull();
    expect(button(root, "Edit layout")).toBeUndefined();
  });

  it("gives the note and an Edit layout that closes the dialog, then opens the editor", async () => {
    const { root, close, push } = render(vi.fn(), false, EDITOR);
    expect(root.querySelector("[data-customize-note]")?.textContent).toContain("Add them to the Details layout");

    button(root, "Edit layout").dispatchEvent(new MouseEvent("click"));
    await settle();

    expect(close).toHaveBeenCalledWith();
    expect(push).toHaveBeenCalledWith(EDITOR);
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

  it("names its primary button Save and submit when a Submit asked", () => {
    const { root } = render(vi.fn(), true);

    expect(button(root, "Save and submit")).toBeDefined();
    expect(button(root, "Continue")).toBeUndefined();
  });

  it("closes with nothing on Cancel", async () => {
    const { root, close } = render();

    button(root, "Cancel").dispatchEvent(new MouseEvent("click"));

    expect(close).toHaveBeenCalledWith();
  });
});
