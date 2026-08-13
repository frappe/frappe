// `page.dialog` (wayfinder ticket 13) as executable claims: the close contract,
// the page binding, attribution, and the layout modes `form` accepts.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";

const confirmSpy = vi.fn();
const dangerSpy = vi.fn();

// The page only borrows `call`, `toast` and the imperative `dialog` namespace;
// the real barrel drags icon plugins in.
vi.mock("frappe-ui", () => ({
  call: vi.fn(),
  toast: { success: vi.fn(), error: vi.fn() },
  dialog: {
    confirm: (args: any) => confirmSpy(args),
    danger: (args: any) => dangerSpy(args),
  },
}));

import { createRecordPage, type RecordPageHost } from "../createRecordPage";
import { registerRecordPage, resetRegistry } from "../registry";
import {
  applyRequired,
  layoutFromFields,
  layoutMode,
  missingRequired,
  pickMetaFields,
  warnAmbiguousLayout,
} from "../formDialogLayout";
import type { FormLayoutSchema } from "../../../components/FormLayout/types";

function makeHost(overrides: Partial<RecordPageHost> = {}): RecordPageHost {
  return {
    doctype: "CRM Deal",
    docname: "CRM-DEAL-1",
    doc: ref({ status: "Open" }),
    meta: ref(null),
    perms: () => ({}),
    isDirty: () => false,
    activeTab: () => "activity",
    save: async () => {},
    reload: async () => {},
    router: {} as any,
    ...overrides,
  };
}

describe("page.dialog.form and open", () => {
  beforeEach(() => {
    resetRegistry();
    confirmSpy.mockReset();
    dangerSpy.mockReset();
  });

  it("resolves with the data the dialog closes with", async () => {
    const { page, dialogs } = createRecordPage(makeHost());
    const promise = page.dialog.form({
      fields: [{ fieldname: "summary", fieldtype: "Small Text" }],
    });

    expect(dialogs.value).toHaveLength(1);
    dialogs.value[0].settle({ summary: "Called back" });

    expect(await promise).toEqual({ summary: "Called back" });
    // The answer settles now; the entry leaves the stack when the host's leave
    // transition ends, so an unmount in that window cannot rewrite the answer.
    expect(dialogs.value).toHaveLength(1);
    dialogs.value[0].dismiss();
    expect(dialogs.value).toHaveLength(0);
  });

  it("keeps a settled answer when the page goes away mid-transition", async () => {
    const controller = createRecordPage(makeHost());
    const promise = controller.page.dialog.form({ fields: [] });

    controller.dialogs.value[0].settle({ summary: "submitted" });
    controller.closeDialogs();

    expect(await promise).toEqual({ summary: "submitted" });
  });

  it("refuses to open once the page has gone away", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const controller = createRecordPage(makeHost());
    controller.closeDialogs();

    expect(await controller.page.dialog.form({ fields: [] })).toBeNull();
    expect(controller.dialogs.value).toHaveLength(0);
    expect(warn).toHaveBeenCalledWith(
      expect.stringContaining("after leaving the record"),
    );
    warn.mockRestore();
  });

  it("resolves null when the dialog is dismissed", async () => {
    const { page, dialogs } = createRecordPage(makeHost());
    const promise = page.dialog.form({ fields: [] });
    dialogs.value[0].settle();
    expect(await promise).toBeNull();
  });

  it("tags the open with the source that ran", async () => {
    registerRecordPage("CRM Deal", {
      refresh: (page) => {
        page.dialog.form({ fields: [] });
      },
    });
    const controller = createRecordPage(makeHost());
    await controller.refresh();

    expect(controller.dialogs.value[0].source).toBe("host");
  });

  it("hands `open` the component and its props, and answers with close(result)", async () => {
    const component = { name: "LogCall" };
    const { page, dialogs } = createRecordPage(makeHost());
    const promise = page.dialog.open(component as any, { deal: "D-1" });

    const entry = dialogs.value[0];
    expect(entry.kind).toBe("component");
    expect(entry.component).toBe(component);
    expect(entry.props).toEqual({ deal: "D-1" });

    entry.settle("logged");
    expect(await promise).toBe("logged");
  });

  it("closes the stack newest-first when the page goes away", async () => {
    const controller = createRecordPage(makeHost());
    const closed: string[] = [];
    const first = controller.page.dialog.form({ title: "first", fields: [] });
    const second = controller.page.dialog.form({ title: "second", fields: [] });
    const titles = controller.dialogs.value.map((entry) => entry.form?.title);
    void first.then(() => closed.push("first"));
    void second.then(() => closed.push("second"));

    controller.closeDialogs();

    expect(await first).toBeNull();
    expect(await second).toBeNull();
    expect(titles).toEqual(["first", "second"]);
    expect(closed).toEqual(["second", "first"]);
    expect(controller.dialogs.value).toHaveLength(0);
  });

  it("warns, naming the source, when a verb fires during a replay", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    registerRecordPage("CRM Deal", {
      refresh: (page) => {
        page.dialog.form({ fields: [] });
      },
    });
    await createRecordPage(makeHost()).refresh();

    expect(warn).toHaveBeenCalledWith(
      expect.stringContaining("host called page.dialog.form during a replay"),
    );
    warn.mockRestore();
  });

  it("does not warn when a verb fires outside a replay", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const { page } = createRecordPage(makeHost());
    page.dialog.form({ fields: [] });
    expect(warn).not.toHaveBeenCalled();
    warn.mockRestore();
  });
});

describe("page.dialog.confirm and danger", () => {
  beforeEach(() => {
    confirmSpy.mockReset();
    dangerSpy.mockReset();
  });

  it("resolves true when confirmed and null when cancelled", async () => {
    confirmSpy.mockImplementation(() => {
      close: vi.fn();
    });
    const { page } = createRecordPage(makeHost());

    const confirmed = page.dialog.confirm({ title: "Sure?" });
    await confirmSpy.mock.calls[0][0].onConfirm({});
    expect(await confirmed).toBe(true);

    const cancelled = page.dialog.confirm({ title: "Sure?" });
    confirmSpy.mock.calls[1][0].onCancel();
    expect(await cancelled).toBeNull();
  });

  it("routes danger through frappe-ui's danger, keeping its schema", async () => {
    dangerSpy.mockImplementation(() => {
      close: vi.fn();
    });
    const { page } = createRecordPage(makeHost());
    page.dialog.danger({ title: "Delete?", message: "Gone for good" });

    expect(dangerSpy.mock.calls[0][0]).toMatchObject({
      title: "Delete?",
      message: "Gone for good",
    });
  });

  it("resolves null for a custom action that only dismisses", async () => {
    confirmSpy.mockImplementation(() => ({ close: vi.fn() }));
    const { page } = createRecordPage(makeHost());
    const promise = page.dialog.confirm({ actions: [{ label: "Cancel" }] });

    await confirmSpy.mock.calls[0][0].actions[0].onClick({});

    expect(await promise).toBeNull();
  });

  it("resolves true for a custom action that acted", async () => {
    confirmSpy.mockImplementation(() => ({ close: vi.fn() }));
    const onClick = vi.fn();
    const { page } = createRecordPage(makeHost());
    const promise = page.dialog.confirm({
      actions: [{ label: "Flag", onClick }],
    });

    await confirmSpy.mock.calls[0][0].actions[0].onClick({});

    expect(onClick).toHaveBeenCalled();
    expect(await promise).toBe(true);
  });

  it("dismisses a native dialog and resolves null when the page goes away", async () => {
    const handle = { close: vi.fn() };
    confirmSpy.mockImplementation(() => handle);
    const controller = createRecordPage(makeHost());
    const promise = controller.page.dialog.confirm({ title: "Sure?" });

    controller.closeDialogs();

    expect(handle.close).toHaveBeenCalled();
    expect(await promise).toBeNull();
  });
});

describe("form layout modes", () => {
  it("takes the first when two modes are given, and warns separately", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    expect(layoutMode({ fields: [], doctype: "Contact" })).toBe("fields");
    expect(warn).not.toHaveBeenCalled();

    warnAmbiguousLayout({ fields: [], doctype: "Contact" });
    expect(warn).toHaveBeenCalledWith(
      expect.stringContaining("mutually exclusive"),
    );
    warn.mockRestore();
  });

  it("warns when fieldnames arrives without a doctype to read them from", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    warnAmbiguousLayout({ fieldnames: ["email"] });
    expect(warn).toHaveBeenCalledWith(
      expect.stringContaining("fieldnames without a doctype"),
    );
    warn.mockRestore();
  });

  it("reads DocField vocabulary, not FieldMeta's", () => {
    const layout = layoutFromFields([
      {
        fieldname: "reason",
        fieldtype: "Small Text",
        label: "Reason",
        reqd: 1,
        depends_on: "eval:doc.status",
      },
    ]);
    const field = layout[0].sections[0].columns[0].fields[0];

    expect(field.reqd).toBe(true);
    expect(field.dependsOn).toBe("eval:doc.status");
  });

  it("picks meta fields in the order asked for, dropping unknown ones", () => {
    const picked = pickMetaFields(
      [
        { fieldname: "a", fieldtype: "Data" },
        { fieldname: "b", fieldtype: "Data" },
        { fieldname: "c", fieldtype: "Data" },
      ],
      ["c", "a", "nope"],
    );

    expect(
      picked[0].sections[0].columns[0].fields.map((f) => f.fieldname),
    ).toEqual(["c", "a"]);
  });

  it("demotes a field the reader may only read, and hides one they may not", () => {
    const picked = pickMetaFields(
      [
        { fieldname: "a", fieldtype: "Data" },
        { fieldname: "b", fieldtype: "Data" },
      ],
      ["a", "b"],
      (field) => (field.fieldname === "a" ? "read" : "none"),
    );
    const fields = picked[0].sections[0].columns[0].fields;

    expect(fields[0].readOnly).toBe(true);
    expect(fields[1].hidden).toBe(true);
  });

  it("forces `required` fieldnames mandatory", () => {
    const layout = applyRequired(
      layoutFromFields([{ fieldname: "email", fieldtype: "Data" }]),
      ["email"],
    );
    expect(layout[0].sections[0].columns[0].fields[0].reqd).toBe(true);
  });
});

describe("mandatory checking", () => {
  const layout: FormLayoutSchema = layoutFromFields([
    {
      fieldname: "summary",
      fieldtype: "Small Text",
      label: "Summary",
      reqd: 1,
    },
    {
      fieldname: "reason",
      fieldtype: "Small Text",
      label: "Reason",
      reqd: 1,
      depends_on: "eval:doc.summary == 'lost'",
    },
  ]);

  it("names the empty mandatory fields by label", () => {
    expect(missingRequired(layout, {})).toEqual(["Summary"]);
  });

  it("does not demand a field its depends_on has hidden", () => {
    expect(missingRequired(layout, { summary: "won" })).toEqual([]);
  });

  it("demands a conditional field once it is on screen", () => {
    expect(missingRequired(layout, { summary: "lost" })).toEqual(["Reason"]);
  });
});
