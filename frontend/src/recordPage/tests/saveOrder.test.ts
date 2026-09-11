// `page.save()` as executable claims: one path, CRM's order, and a clean doc that sends nothing.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";

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

import { createRecordPage, SAVE_VETO, type RecordPageHost } from "../createRecordPage";
import { registerRecordPage, resetRegistry } from "../registry";

function makeHost(overrides: Partial<RecordPageHost> = {}) {
  const order: string[] = [];
  const doc = ref<Record<string, any>>({ status: "Open", probability: 50 });
  const host: RecordPageHost = {
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
    ...overrides,
  };
  return { host, order, doc };
}

beforeEach(() => {
  resetRegistry();
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

    await expect(controller.page.save()).rejects.toThrow("Win chance is a percentage");
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

    await expect(controller.page.save()).rejects.toThrow("417");
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

  it("a veto rejects under its own name, keeping the script's message", async () => {
    const { host } = makeHost();
    registerRecordPage("CRM Deal", {
      beforeSave: () => {
        throw new Error("Win chance is a percentage");
      },
    });
    const controller = createRecordPage(host);

    const rejection = await controller.page.save().catch((e) => e);

    expect(rejection.name).toBe(SAVE_VETO);
    expect(rejection.message).toBe("Win chance is a percentage");
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
    expect(second).toBe(first);
    release();
    await Promise.all([first, second]);

    expect(order).toEqual(["beforeSave", "write", "afterSave"]);
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
});
