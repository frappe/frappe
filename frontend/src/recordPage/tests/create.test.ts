// `page.create`: the shell's `create` act, given only the values, and quiet once the page has gone.
import { afterEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";

vi.mock("frappe-ui", () => ({
  call: vi.fn(),
  toast: { success: vi.fn(), error: vi.fn() },
  dialog: { confirm: vi.fn(), danger: vi.fn() },
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

import { acts, ActDenied } from "@/acts/dispatcher";
import { createRecordPage, type RecordPageHost } from "../createRecordPage";

let release = () => {};
afterEach(() => release());

/** A shell surface holding only `shell.create`, which runs `create` with the act's value. */
function shellCreate(create: (value: unknown) => unknown) {
  release = acts.register({
    surfaces: { shell: () => [{ item: { name: "create", run: (_shell, value) => create(value) }, hidden: false }] },
    context: () => undefined,
    passes: () => false,
    settled: () => undefined,
    hold: async (work) => work(),
    failed: () => {},
  });
}

function makeHost(overrides: Partial<RecordPageHost> = {}): RecordPageHost {
  return {
    doctype: "CRM Deal",
    docname: "CRM-DEAL-1",
    doc: ref({ status: "Open" }),
    saved: ref({ status: "Open" }),
    meta: ref(null),
    perms: () => ({}),
    isDirty: () => false,
    activeTab: () => "activity",
    activateTab: () => {},
    save: async () => {},
    reload: async () => {},
    router: {} as any,
    activityRows: () => [],
    scrollToActivity: async () => true,
    reloadActivity: async () => {},
    fileRows: () => [],
    reloadFiles: async () => {},
    ...overrides,
  };
}

describe("page.create", () => {
  it("runs shell.create with the doctype and only the values, and resolves with its answer", async () => {
    const create = vi.fn(async () => ({ name: "CONTACT-1" }));
    shellCreate(create);
    const { page } = createRecordPage(makeHost());

    const created = await page.create("Contact", {
      values: { company: "Acme" },
      onSave: () => {},
    } as any);

    expect(create).toHaveBeenCalledWith({ doctype: "Contact", values: { company: "Acme" } });
    expect(created).toEqual({ name: "CONTACT-1" });
  });

  it("passes no values when the script gives none", async () => {
    const create = vi.fn(async () => null);
    shellCreate(create);
    const { page } = createRecordPage(makeHost());

    expect(await page.create("Contact")).toBeNull();
    expect(create).toHaveBeenCalledWith({ doctype: "Contact", values: undefined });
  });

  it("resolves null without opening once the page has left", async () => {
    const create = vi.fn(async () => ({ name: "CONTACT-1" }));
    shellCreate(create);
    const controller = createRecordPage(makeHost());
    controller.leave();

    expect(await controller.page.create("Contact", { values: { company: "Acme" } })).toBeNull();
    expect(create).not.toHaveBeenCalled();
  });

  it("rejects with ActDenied when no shell holds the act", async () => {
    const { page } = createRecordPage(makeHost());

    const denied = await page.create("Contact").catch((error) => error);
    expect(denied).toBeInstanceOf(ActDenied);
    expect(denied).toMatchObject({ act: "shell.create", reason: "missing" });
  });
});
