// Submit and Cancel as executable claims: the event order, the veto, and a confirm every caller waits on.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";

vi.mock("frappe-ui", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
  frappeRequest: vi.fn(),
}));
vi.mock("@framework/ui/api", () => ({
  runMethod: vi.fn(async () => ({ data: null })),
  getMeta: vi.fn(async () => ({ data: null, children: [] })),
}));
vi.mock("@/i18n", () => ({ __: (text: string) => text }));

import { toast } from "frappe-ui";
import { createRecordPage, SAVE_VETO, type RecordPageHost } from "../createRecordPage";
import { fieldsToLayout } from "@framework/ui/FormLayout";
import { registerRecordPage, resetRegistry } from "../registry";
import { cancelledError, SAVE_CANCELLED } from "@/pages/record/saveResponse";
import { docstatusItems } from "@/pages/record/docstatusActs";

const controllers: ReturnType<typeof createRecordPage>[] = [];

function makePage(overrides: Partial<RecordPageHost> = {}, docstatus = 0) {
  const order: string[] = [];
  const meta = { name: "Invoice", is_submittable: 1, fields: [] };
  const host: RecordPageHost = {
    app: "frappe",
    doctype: "Invoice",
    docname: "INV-1",
    doc: ref({ docstatus }),
    saved: ref({ docstatus }),
    meta: ref(meta),
    perms: () => ({ read: 1, write: 1, submit: 1, cancel: 1 }),
    isDirty: () => false,
    activeTab: () => "details",
    activateTab: () => {},
    save: async () => {},
    confirmDocstatus: async (act) => (order.push(`confirm ${act}`), true),
    submit: async () => void order.push("submit call"),
    cancel: async () => void order.push("cancel call"),
    reload: async () => {},
    router: {} as any,
    activityRows: () => [],
    scrollToActivity: async () => true,
    reloadActivity: async () => {},
    fileRows: () => [],
    reloadFiles: async () => {},
    ...overrides,
  };
  const controller = createRecordPage(host);
  controllers.push(controller);
  controller.header.provideBuiltins(() => [
    { name: "save", label: "Save", run: (page) => page.save() },
    ...docstatusItems({ meta, saved: host.saved.value, dirty: false, canWrite: true }, (act) => controller[act]()),
  ]);
  return { controller, page: controller.page, order };
}

beforeEach(() => {
  vi.mocked(toast.error).mockClear();
  resetRegistry();
  vi.spyOn(console, "warn").mockImplementation(() => {});
});

afterEach(() => {
  for (const controller of controllers.splice(0)) controller.leave();
  vi.restoreAllMocks();
});

describe("Submit", () => {
  it("confirms first, then fires beforeSubmit, the host's call, then afterSubmit", async () => {
    const { controller, order } = makePage();
    registerRecordPage("Invoice", {
      beforeSubmit: () => void order.push("beforeSubmit"),
      afterSubmit: () => void order.push("afterSubmit"),
    });

    await controller.submit();

    expect(order).toEqual(["confirm submit", "beforeSubmit", "submit call", "afterSubmit"]);
  });

  it("a beforeSubmit throw vetoes after the confirm: nothing is sent and afterSubmit never fires", async () => {
    const { controller, order } = makePage();
    registerRecordPage("Invoice", {
      beforeSubmit: () => {
        throw new Error("Customer is on hold");
      },
      afterSubmit: () => void order.push("afterSubmit"),
    });

    const refused = await controller.submit().catch((error) => error);

    expect(refused).toMatchObject({ name: SAVE_VETO, message: "Customer is on hold" });
    expect(order).toEqual(["confirm submit"]);
  });

  it("refuses when beforeSubmit left unsaved edits, rather than submitting without them", async () => {
    const dirty = ref(false);
    const { controller, order } = makePage({ isDirty: () => dirty.value });
    registerRecordPage("Invoice", { beforeSubmit: () => void (dirty.value = true) });

    const refused = await controller.submit().catch((error) => error);

    expect(refused).toMatchObject({ name: SAVE_VETO, message: expect.stringContaining("Save it") });
    expect(order).toEqual(["confirm submit"]);
  });

  it("lets beforeSubmit save its edits first", async () => {
    const dirty = ref(false);
    const { controller, page, order } = makePage({
      isDirty: () => dirty.value,
      save: async () => void (dirty.value = false),
    });
    registerRecordPage("Invoice", {
      beforeSubmit: async () => {
        dirty.value = true;
        await page.save();
      },
    });

    await controller.submit();

    expect(order).toEqual(["confirm submit", "submit call"]);
  });

  it("a declined confirm fires no event and sends nothing", async () => {
    const declined = makePage({ confirmDocstatus: async () => false });
    registerRecordPage("Invoice", {
      beforeSubmit: () => void declined.order.push("beforeSubmit"),
      afterSubmit: () => void declined.order.push("afterSubmit"),
    });

    await declined.controller.submit();

    expect(declined.order).toEqual([]);
  });

  it("fires no afterSubmit when the call was queued, but still fires beforeSubmit", async () => {
    const queued = makePage({
      submit: async () => (queued.order.push("submit call"), { queued: true }),
    });
    registerRecordPage("Invoice", {
      beforeSubmit: () => void queued.order.push("beforeSubmit"),
      afterSubmit: () => void queued.order.push("afterSubmit"),
    });

    await queued.controller.submit();

    expect(queued.order).toEqual(["confirm submit", "beforeSubmit", "submit call"]);
  });

  it("fires no afterSubmit when the call fails", async () => {
    const failed = makePage({
      submit: async () => {
        throw new Error("Insufficient stock");
      },
    });
    registerRecordPage("Invoice", { afterSubmit: () => void failed.order.push("afterSubmit") });

    await expect(failed.controller.submit()).rejects.toThrow("Insufficient stock");

    expect(failed.order).toEqual(["confirm submit"]);
  });

  it("page.run waits for the confirm: no event fires and it resolves only once the reader answers", async () => {
    let answer!: (confirmed: boolean) => void;
    const asked = new Promise<boolean>((resolve) => (answer = resolve));
    const { controller, page, order } = makePage({ confirmDocstatus: () => asked });
    registerRecordPage("Invoice", {
      beforeSubmit: () => void order.push("beforeSubmit"),
      afterSubmit: () => void order.push("afterSubmit"),
    });
    await controller.refresh();

    const done = vi.fn();
    const running = page.run("header.submit").then(done);
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(done).not.toHaveBeenCalled();
    expect(order).toEqual([]);

    answer(true);
    await running;
    expect(order).toEqual(["beforeSubmit", "submit call", "afterSubmit"]);
  });

  it("a second Submit while the first is open joins it", async () => {
    let answer!: (confirmed: boolean) => void;
    const confirmDocstatus = vi.fn(() => new Promise<boolean>((resolve) => (answer = resolve)));
    const { controller } = makePage({ confirmDocstatus });

    const first = controller.submit();
    const second = controller.submit();
    await vi.waitFor(() => expect(confirmDocstatus).toHaveBeenCalled());
    answer(true);
    await Promise.all([first, second]);

    expect(confirmDocstatus).toHaveBeenCalledTimes(1);
  });
});

describe("Submit with a mandatory field the layout does not show", () => {
  const hidden = fieldsToLayout([{ fieldname: "batch", fieldtype: "Data", label: "Batch", reqd: true }]);

  function makeDraft(asked: Record<string, any> | null, values: Record<string, any> = {}) {
    const doc = ref<Record<string, any>>({ docstatus: 0, ...values });
    const askRequired = vi.fn(async (_layout: unknown, submitting: boolean) => {
      order.push(`dialog ${submitting ? "save and submit" : "continue"}`);
      if (!asked) throw cancelledError();
      return asked;
    });
    const { controller, order } = makePage({
      doc,
      offLayout: () => hidden,
      askRequired,
      save: async () => void order.push(`save ${doc.value.batch}`),
    });
    registerRecordPage("Invoice", {
      beforeSave: () => void order.push("beforeSave"),
      afterSave: () => void order.push("afterSave"),
      beforeSubmit: () => void order.push("beforeSubmit"),
      afterSubmit: () => void order.push("afterSubmit"),
    });
    return { controller, order, askRequired };
  }

  it("confirms, asks, saves through beforeSave and afterSave, then submits with no second confirm", async () => {
    const { controller, order } = makeDraft({ batch: "B1" });

    await controller.submit();

    expect(order).toEqual([
      "confirm submit",
      "beforeSave",
      "dialog save and submit",
      "save B1",
      "afterSave",
      "beforeSubmit",
      "submit call",
      "afterSubmit",
    ]);
  });

  it("a cancelled dialog sends nothing and fires no beforeSubmit or afterSubmit", async () => {
    const { controller, order } = makeDraft(null);

    await expect(controller.submit()).rejects.toMatchObject({ name: SAVE_CANCELLED });

    expect(order).toEqual(["confirm submit", "beforeSave", "dialog save and submit"]);
  });

  it("a declined confirm never opens the dialog", async () => {
    const askRequired = vi.fn(async () => ({ batch: "B1" }));
    const declined = makePage({ confirmDocstatus: async () => false, offLayout: () => hidden, askRequired });

    await declined.controller.submit();

    expect(askRequired).not.toHaveBeenCalled();
    expect(declined.order).toEqual([]);
  });

  it("refuses when afterSave left unsaved edits, rather than submitting without them", async () => {
    let dirty = false;
    const { controller, order } = makePage({
      doc: ref({ docstatus: 0 }),
      isDirty: () => dirty,
      offLayout: () => hidden,
      askRequired: async () => ({ batch: "B1" }),
    });
    registerRecordPage("Invoice", { afterSave: () => void (dirty = true) });

    await expect(controller.submit()).rejects.toMatchObject({ name: SAVE_VETO });

    expect(order).toEqual(["confirm submit"]);
  });

  it("a clean draft with every mandatory value saves nothing and skips the dialog", async () => {
    const { controller, order, askRequired } = makeDraft({ batch: "B1" }, { batch: "B0" });

    await controller.submit();

    expect(askRequired).not.toHaveBeenCalled();
    expect(order).toEqual(["confirm submit", "beforeSubmit", "submit call", "afterSubmit"]);
  });
});

describe("page.doc.docstatus", () => {
  it("refuses a script write, so the docstatus moves only through the acts", () => {
    const { page } = makePage();
    const doc = page.doc as Record<string, any>;

    expect(() => (doc.docstatus = 1)).toThrow(/page\.doc\.docstatus is read-only/);
    expect(() => delete doc.docstatus).toThrow(/read-only/);
    expect(doc.docstatus).toBe(0);
    expect(() => (doc.title = "Draft")).not.toThrow();
    expect(page.doc).toBe(page.doc);
  });
});

describe("Cancel", () => {
  it("confirms first, then fires beforeCancel, the host's call, then afterCancel", async () => {
    const { controller, order } = makePage({}, 1);
    registerRecordPage("Invoice", {
      beforeCancel: () => void order.push("beforeCancel"),
      afterCancel: () => void order.push("afterCancel"),
    });

    await controller.cancel();

    expect(order).toEqual(["confirm cancel", "beforeCancel", "cancel call", "afterCancel"]);
  });

  it("fires no afterCancel when the call was queued, but still fires beforeCancel", async () => {
    const queued = makePage({ cancel: async () => (queued.order.push("cancel call"), { queued: true }) }, 1);
    registerRecordPage("Invoice", {
      beforeCancel: () => void queued.order.push("beforeCancel"),
      afterCancel: () => void queued.order.push("afterCancel"),
    });

    await queued.controller.cancel();

    expect(queued.order).toEqual(["confirm cancel", "beforeCancel", "cancel call"]);
  });

  it("a beforeCancel throw vetoes: nothing is sent and afterCancel never fires", async () => {
    const { controller, order } = makePage({}, 1);
    registerRecordPage("Invoice", {
      beforeCancel: () => {
        throw new Error("Paid invoices stay");
      },
      afterCancel: () => void order.push("afterCancel"),
    });

    const refused = await controller.cancel().catch((error) => error);

    expect(refused).toMatchObject({ name: SAVE_VETO, message: "Paid invoices stay" });
    expect(order).toEqual(["confirm cancel"]);
  });

  it("page.run reaches header.cancel on a submitted record and header.submit is absent", async () => {
    const { controller, page, order } = makePage({}, 1);
    await controller.refresh();

    await page.run("header.cancel");
    const missing = await page.run("header.submit").catch((error) => error);

    expect(order).toEqual(["confirm cancel", "cancel call"]);
    expect(missing).toMatchObject({ reason: "missing" });
  });

  it("page.run refuses header.cancel without the cancel right", async () => {
    const { controller, page, order } = makePage({ perms: () => ({ read: 1, write: 1, submit: 1 }) }, 1);
    await controller.refresh();

    const denied = await page.run("header.cancel").catch((error) => error);

    expect(denied).toMatchObject({ reason: "right" });
    expect(order).toEqual([]);
  });
});

describe("a failing act toasts once, however many callers joined it", () => {
  const failure = () => {
    throw new Error("Insufficient stock");
  };

  it.each([
    ["Submit", "header.submit", { submit: failure }, 0],
    ["Cancel", "header.cancel", { cancel: failure }, 1],
    ["Save", "header.save", { isDirty: () => true }, 0],
  ] as const)("%s: two clicks give one toast", async (_act, name, overrides, docstatus) => {
    let open!: () => void;
    const gate = new Promise<void>((resolve) => (open = resolve));
    const { controller } = makePage(
      {
        ...overrides,
        confirmDocstatus: async () => (await gate, true),
        save: async () => (await gate, failure()),
      },
      docstatus,
    );

    const clicks = Promise.all([controller.perform(name), controller.perform(name)]);
    await new Promise((resolve) => setTimeout(resolve));
    open();
    await clicks;

    expect(toast.error).toHaveBeenCalledExactlyOnceWith("Insufficient stock");
  });

  it.each([
    ["Submit", "header.submit", { submit: failure }, 0],
    ["Cancel", "header.cancel", { cancel: failure }, 1],
  ] as const)("%s: every caller still gets the rejection", async (_act, name, overrides, docstatus) => {
    const { page } = makePage({ ...overrides }, docstatus);

    const both = await Promise.allSettled([page.run(name), page.run(name)]);

    expect(both.map((one) => one.status)).toEqual(["rejected", "rejected"]);
    expect(toast.error).not.toHaveBeenCalled();
  });

  it("Save: every caller gets false and the failure shows once", async () => {
    const { page } = makePage({ save: async () => failure(), isDirty: () => true });

    expect(await Promise.all([page.run("header.save"), page.run("header.save")])).toEqual([false, false]);
    expect(toast.error).toHaveBeenCalledExactlyOnceWith("Insufficient stock");
  });

  it("a later failure of the same act toasts again", async () => {
    const { controller } = makePage({ submit: failure });

    await controller.perform("header.submit");
    await controller.perform("header.submit");

    expect(toast.error).toHaveBeenCalledTimes(2);
  });

  it("hands the host's actFailed one call for two joined callers", async () => {
    const actFailed = vi.fn();
    const { controller } = makePage({ submit: failure, actFailed });

    await Promise.all([controller.perform("header.submit"), controller.perform("header.submit")]);

    expect(actFailed).toHaveBeenCalledTimes(1);
  });
});
