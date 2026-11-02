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

import { createRecordPage, SAVE_VETO, type RecordPageHost } from "../createRecordPage";
import { registerRecordPage, resetRegistry } from "../registry";
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
  controller.header.provideBuiltins(() =>
    docstatusItems({ meta, saved: host.saved.value, dirty: false, canWrite: true }, (act) => controller[act]()),
  );
  return { controller, page: controller.page, order };
}

beforeEach(() => {
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
