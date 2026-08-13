// The `form` host's behaviours (wayfinder ticket 13 §3), which live in the
// component rather than in `dialog.ts`: the throw that holds the dialog open,
// custom actions, and the dismissal paths that answer the opener.
import { describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick } from "vue";

// The dialog chrome is frappe-ui's; here it is a passthrough so the test reads
// the form's own behaviour, not reka-ui's transitions.
vi.mock("frappe-ui", () => ({
  Dialog: defineComponent({
    props: { open: { type: Boolean, default: true } },
    emits: ["update:open", "after-leave"],
    setup(props, { slots }) {
      return () =>
        props.open
          ? h("div", [h("div", slots.default?.()), h("div", slots.actions?.())])
          : null;
    },
  }),
  Button: defineComponent({
    props: { label: String, loading: Boolean, disabled: Boolean },
    setup(props, { attrs }) {
      return () =>
        h("button", { ...attrs, disabled: props.disabled }, props.label);
    },
  }),
  ErrorMessage: defineComponent({
    props: { message: String },
    setup: (props) => () => h("p", { class: "error" }, props.message),
  }),
  createResource: () => ({
    data: null,
    loading: false,
    fetch() {},
    reload() {},
  }),
  frappeRequest: vi.fn(),
  call: vi.fn(),
  toast: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("../../../components/FormLayout", () => ({
  // The real FormLayout is exercised in Chrome; here it only has to own the doc.
  FormLayout: defineComponent({
    props: {
      layout: { type: Array, required: true },
      doc: { type: Object, required: true },
    },
    emits: ["update:doc"],
    setup: () => () => h("form"),
  }),
}));

import PageFormDialog from "../PageFormDialog.vue";
import type { PageDialogEntry } from "../dialog";
import type { PageDialogFormOptions } from "../types";

function makeEntry(form: PageDialogFormOptions) {
  const entry: PageDialogEntry & { settled: any[] } = {
    id: 1,
    source: "page-script:deal-hello",
    kind: "form",
    props: {},
    options: {},
    form,
    settled: [],
    // Idempotent, like the real one: the component always flips `isOpen` after
    // closing, and that dismissal must not overwrite the answer already given.
    settle: (result: any = null) => {
      if (!entry.settled.length) entry.settled.push(result);
    },
    dismiss: vi.fn(),
  };
  return entry;
}

const FIELDS = [{ fieldname: "note", fieldtype: "Data", label: "Note" }];

/** Mount the dialog into a throwaway root; no test-utils dependency to add. */
function render(entry: PageDialogEntry) {
  const root = document.createElement("div");
  document.body.appendChild(root);
  createApp(PageFormDialog, { entry }).mount(root);
  return root;
}

function button(root: HTMLElement, label: string) {
  return [...root.querySelectorAll("button")].find(
    (element) => element.textContent?.trim() === label,
  );
}

/** Let a click's async handler and the re-render it causes both land. */
async function settle() {
  await nextTick();
  await Promise.resolve();
  await nextTick();
}

async function click(root: HTMLElement, label: string) {
  button(root, label)!.dispatchEvent(new MouseEvent("click"));
  await settle();
}

describe("the form host", () => {
  it("holds the dialog open with the error inline when onSubmit throws", async () => {
    const error = vi.spyOn(console, "error").mockImplementation(() => {});
    const entry = makeEntry({
      fields: FIELDS,
      onSubmit: () => {
        throw new Error("Not allowed on a won deal");
      },
    });
    const root = render(entry);

    await click(root, "Submit");

    expect(root.querySelector(".error")!.textContent).toBe(
      "Not allowed on a won deal",
    );
    expect(entry.settled).toEqual([]);
    expect(button(root, "Submit")).toBeTruthy();
    // The reader sees the message; the console names the script behind it.
    expect(error).toHaveBeenCalledWith(
      expect.stringContaining("page-script:deal-hello"),
      expect.anything(),
    );
    error.mockRestore();
  });

  it("resolves with the field values on a clean submit", async () => {
    const onSubmit = vi.fn();
    const entry = makeEntry({
      fields: FIELDS,
      defaults: { note: "hi" },
      onSubmit,
    });
    const root = render(entry);

    await click(root, "Submit");

    expect(onSubmit).toHaveBeenCalledWith({ note: "hi" });
    expect(entry.settled).toEqual([{ note: "hi" }]);
  });

  it("refuses a submit that leaves a mandatory field empty", async () => {
    const onSubmit = vi.fn();
    const entry = makeEntry({
      fields: [
        { fieldname: "note", fieldtype: "Data", label: "Note", reqd: 1 },
      ],
      onSubmit,
    });
    const root = render(entry);

    await click(root, "Submit");

    expect(root.querySelector(".error")!.textContent).toBe(
      "Please fill in Note",
    );
    expect(onSubmit).not.toHaveBeenCalled();
    expect(entry.settled).toEqual([]);
  });

  it("hands a custom action { data, close, validate } and lets it answer", async () => {
    let seen: any = null;
    const entry = makeEntry({
      fields: FIELDS,
      defaults: { note: "why" },
      actions: [
        {
          label: "Reject",
          onClick: (context) => {
            seen = context;
            context.close("rejected");
          },
        },
      ],
    });
    const root = render(entry);

    expect(button(root, "Submit")).toBeUndefined();
    await click(root, "Reject");

    expect(seen.data).toEqual({ note: "why" });
    expect(typeof seen.validate).toBe("function");
    expect(entry.settled).toEqual(["rejected"]);
  });

  it("validates and closes with the data for a custom action with no onClick", async () => {
    const entry = makeEntry({
      fields: FIELDS,
      defaults: { note: "ok" },
      actions: [{ label: "Save" }],
    });
    const root = render(entry);

    await click(root, "Save");

    expect(entry.settled).toEqual([{ note: "ok" }]);
  });

  it("runs onCancel and resolves null when the page goes away", async () => {
    const onCancel = vi.fn();
    const entry = makeEntry({ fields: FIELDS, onCancel });
    render(entry);

    // What `closeAll` does to a live dialog.
    entry.onDismissed?.();
    entry.settle(null);

    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(entry.settled).toEqual([null]);
  });

  it("does not run onCancel after the reader already submitted", async () => {
    const onCancel = vi.fn();
    const entry = makeEntry({
      fields: FIELDS,
      defaults: { note: "x" },
      onCancel,
    });
    const root = render(entry);

    await click(root, "Submit");
    entry.onDismissed?.();

    expect(onCancel).not.toHaveBeenCalled();
    expect(entry.settled).toEqual([{ note: "x" }]);
  });
});
