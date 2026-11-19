// `page.save()` as executable claims: one path, CRM's order, and a clean doc that sends nothing.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import { fieldsToLayout } from "@framework/ui/FormLayout";
import type { FormLayoutSchema } from "@framework/ui/FormLayout/types";

vi.mock("frappe-ui", () => ({
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

import { toast } from "frappe-ui";
import { createRecordPage, SAVE_VETO, type RecordPageHost } from "../createRecordPage";
import { registerRecordPage, resetRegistry } from "../registry";
import { cancelledError } from "@/pages/record/saveResponse";

function makeHost(overrides: Partial<RecordPageHost> = {}) {
  const order: string[] = [];
  const doc = ref<Record<string, any>>({ status: "Open", probability: 50 });
  const host: RecordPageHost = {
    app: "frappe",
    doctype: "CRM Deal",
    docname: "CRM-DEAL-1",
    doc,
    saved: ref({ status: "Open", probability: 50 }),
    meta: ref({ fields: [] }),
    perms: () => ({}),
    isDirty: () => true,
    activeTab: () => "",
    activateTab: () => {},
    save: async () => void order.push("write"),
    reload: async () => {},
    router: {} as any,
    activityRows: () => [],
    scrollToActivity: async () => true,
    reloadActivity: async () => {},
    fileRows: () => [],
    reloadFiles: async () => {},
    ...overrides,
  };
  return { host, order, doc };
}

beforeEach(() => {
  resetRegistry();
  vi.mocked(toast.error).mockClear();
  vi.spyOn(console, "warn").mockImplementation(() => {});
});

describe("page.save()", () => {
  it("flushes the pending edit, then beforeSave, the write, then afterSave", async () => {
    const { host, order } = makeHost();
    registerRecordPage("CRM Deal", {
      status: () => void order.push("status"),
      beforeSave: () => void order.push("beforeSave"),
      afterSave: () => void order.push("afterSave"),
    });
    const controller = createRecordPage(host);

    controller.commits.pending("status", "Won");
    await controller.page.save();

    expect(order).toEqual(["status", "beforeSave", "write", "afterSave"]);
  });

  it("a beforeSave throw vetoes: nothing is written and afterSave never fires", async () => {
    const { host, order } = makeHost();
    registerRecordPage("CRM Deal", {
      beforeSave: () => {
        throw new Error("Win chance is a percentage");
      },
      afterSave: () => void order.push("afterSave"),
    });
    const controller = createRecordPage(host);

    expect(await controller.page.save()).toBe(false);
    expect(toast.error).toHaveBeenCalledExactlyOnceWith("Win chance is a percentage");
    expect(order).toEqual([]);
  });

  it("a rejected write fires no afterSave", async () => {
    const { host, order } = makeHost({
      save: async () => {
        throw new Error("Save failed with 417");
      },
    });
    registerRecordPage("CRM Deal", {
      afterSave: () => void order.push("afterSave"),
    });
    const controller = createRecordPage(host);

    expect(await controller.page.save()).toBe(false);
    expect(toast.error).toHaveBeenCalledExactlyOnceWith("Save failed with 417");
    expect(order).toEqual([]);
  });

  it("a clean doc resolves at once: no flush, no handlers, no write", async () => {
    const { host, order } = makeHost({ isDirty: () => false });
    registerRecordPage("CRM Deal", {
      status: () => void order.push("status"),
      beforeSave: () => void order.push("beforeSave"),
      afterSave: () => void order.push("afterSave"),
    });
    const controller = createRecordPage(host);

    controller.commits.pending("status", "Won");
    await controller.page.save();

    expect(order).toEqual([]);
  });

  it("a veto reaches the host under its own name, keeping the script's message", async () => {
    const saveFailed = vi.fn();
    const { host } = makeHost({ saveFailed });
    registerRecordPage("CRM Deal", {
      beforeSave: () => {
        throw new Error("Win chance is a percentage");
      },
    });
    const controller = createRecordPage(host);

    expect(await controller.page.save()).toBe(false);

    const [reported] = saveFailed.mock.calls[0];
    expect(reported.name).toBe(SAVE_VETO);
    expect(reported.message).toBe("Win chance is a percentage");
    expect(toast.error).not.toHaveBeenCalled();
  });

  it("resolves true after the write and afterSave", async () => {
    const { host, order } = makeHost();
    registerRecordPage("CRM Deal", { afterSave: () => void order.push("afterSave") });
    const controller = createRecordPage(host);

    expect(await controller.page.save()).toBe(true);

    expect(order).toEqual(["write", "afterSave"]);
    expect(toast.error).not.toHaveBeenCalled();
  });

  it("resolves true when afterSave throws: the record is saved and the handler is isolated", async () => {
    const { host, order } = makeHost();
    registerRecordPage("CRM Deal", {
      afterSave: () => {
        throw new Error("after failed");
      },
    });
    const controller = createRecordPage(host);

    expect(await controller.page.save()).toBe(true);

    expect(order).toEqual(["write"]);
  });

  it("two callers that joined one failing save both get false and the failure shows once", async () => {
    let fail!: (error: Error) => void;
    const { host } = makeHost({ save: () => new Promise<void>((_, reject) => (fail = reject)) });
    const controller = createRecordPage(host);

    const both = Promise.all([controller.page.save(), controller.page.save()]);
    await vi.waitFor(() => expect(fail).toBeTypeOf("function"));
    fail(new Error("Mandatory: Title"));

    expect(await both).toEqual([false, false]);
    expect(toast.error).toHaveBeenCalledExactlyOnceWith("Mandatory: Title");
    expect(controller.isSaving.value).toBe(false);
  });

  it("a page the reader has left resolves false and writes nothing", async () => {
    const { host, order } = makeHost();
    const controller = createRecordPage(host);
    controller.leave();

    expect(await controller.page.save()).toBe(false);
    expect(order).toEqual([]);
  });

  it("two saves mid-flight run the handlers and the write once", async () => {
    let release!: () => void;
    const { host, order } = makeHost({
      save: async () => {
        order.push("write");
        await new Promise<void>((resolve) => (release = resolve));
      },
    });
    registerRecordPage("CRM Deal", {
      beforeSave: () => void order.push("beforeSave"),
      afterSave: () => void order.push("afterSave"),
    });
    const controller = createRecordPage(host);

    const first = controller.page.save();
    while (!order.includes("write")) await Promise.resolve();
    const second = controller.page.save();
    release();
    expect(await Promise.all([first, second])).toEqual([true, true]);

    expect(order).toEqual(["beforeSave", "write", "afterSave"]);
  });

  it("is saving from the call until afterSave settles, and a save after a failed one sends again", async () => {
    let fail = true;
    const { host, order } = makeHost({
      save: async () => {
        order.push("write");
        if (fail) throw new Error("Save failed with 417");
      },
    });
    registerRecordPage("CRM Deal", {
      afterSave: () => void order.push(`afterSave saving=${controller.isSaving.value}`),
    });
    const controller = createRecordPage(host);

    const failed = controller.page.save();
    expect(controller.isSaving.value).toBe(true);
    expect(await failed).toBe(false);
    expect(controller.isSaving.value).toBe(false);
    fail = false;
    await controller.page.save();

    expect(order).toEqual(["write", "write", "afterSave saving=true"]);
    expect(controller.isSaving.value).toBe(false);
  });

  it("a page left while beforeSave runs writes nothing", async () => {
    let release!: () => void;
    const { host, order } = makeHost();
    registerRecordPage("CRM Deal", {
      beforeSave: () => new Promise<void>((resolve) => (release = resolve)),
    });
    const controller = createRecordPage(host);

    const saving = controller.page.save();
    while (!release) await Promise.resolve();
    controller.leave();
    release();
    await saving;

    expect(order).toEqual([]);
  });

  it("the flushed handler's own write lands before beforeSave reads the doc", async () => {
    const { host, doc } = makeHost();
    let seen: number | undefined;
    registerRecordPage("CRM Deal", {
      status: (page) => {
        if (page.doc.status === "Won") page.doc.probability = 100;
      },
      beforeSave: (page) => void (seen = page.doc.probability),
    });
    const controller = createRecordPage(host);

    doc.value.status = "Won";
    controller.commits.pending("status", "Won");
    await controller.page.save();

    expect(seen).toBe(100);
  });

  it("the controller's channel commits into the same dispatch a script's handlers hear", async () => {
    const { host, order } = makeHost();
    registerRecordPage("CRM Deal", {
      status: () => void order.push("status"),
    });
    const controller = createRecordPage(host);

    await controller.commits.commit("status", "Won");
    await controller.page.save();

    expect(order).toEqual(["status", "write"]);
  });

  describe("with a mandatory field the layout does not show", () => {
    const offLayout = () =>
      fieldsToLayout([
        { fieldname: "batch", fieldtype: "Data", label: "Batch", reqd: true },
        { fieldname: "note", fieldtype: "Data", label: "Note" },
      ]);

    it("asks for it after the form is complete, merges the values, then writes", async () => {
      const askRequired = vi.fn(async (_layout: FormLayoutSchema) => ({ batch: "B1" }));
      const { host, order, doc } = makeHost({
        offLayout,
        askRequired,
        save: async () => void order.push("write"),
      });
      const controller = createRecordPage(host);

      await controller.page.save();

      const asked = askRequired.mock.calls[0][0];
      expect(asked[0].sections[0].columns[0].fields.map((one: any) => one.fieldname)).toEqual(["batch"]);
      expect(doc.value.batch).toBe("B1");
      expect(order).toEqual(["write"]);
    });

    it("writes nothing when the reader cancels, and the draft stays as it is", async () => {
      const cancelled = cancelledError();
      const { host, order, doc } = makeHost({
        offLayout,
        askRequired: async () => {
          throw cancelled;
        },
      });
      const controller = createRecordPage(host);

      expect(await controller.page.save()).toBe(false);
      expect(order).toEqual([]);
      expect(doc.value.batch).toBeUndefined();
    });

    it("asks again for a field that the first answer made mandatory", async () => {
      const chained = () =>
        fieldsToLayout([
          { fieldname: "kind", fieldtype: "Data", label: "Kind", reqd: true },
          { fieldname: "detail", fieldtype: "Data", label: "Detail", mandatoryDependsOn: "eval:doc.kind == 'A'" },
        ]);
      const answers = [{ kind: "A" }, { detail: "d" }];
      const askRequired = vi.fn(async () => answers.shift()!);
      const { host, doc } = makeHost({ offLayout: chained, askRequired });
      const controller = createRecordPage(host);

      await controller.page.save();

      expect(askRequired).toHaveBeenCalledTimes(2);
      expect(doc.value).toMatchObject({ kind: "A", detail: "d" });
    });

    it("does not ask when the field already has a value", async () => {
      const askRequired = vi.fn(async () => ({}));
      const { host, order, doc } = makeHost({ offLayout, askRequired });
      doc.value.batch = "B0";
      const controller = createRecordPage(host);

      await controller.page.save();

      expect(askRequired).not.toHaveBeenCalled();
      expect(order).toEqual(["write"]);
    });
  });
});
