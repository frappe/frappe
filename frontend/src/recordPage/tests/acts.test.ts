// `page.run` and the dispatcher: an act is a surface item with `run`, found as drawn after the
// replay, and refused with `ActDenied` when it is missing, hidden or its right fails.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import type { Session } from "@framework/ui/api";

const state = vi.hoisted(() => ({ metas: {} as Record<string, any> }));

vi.mock("frappe-ui", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
  frappeRequest: vi.fn(),
}));
vi.mock("@framework/ui/api", () => ({
  runMethod: vi.fn(async () => ({ data: null })),
  getMeta: vi.fn(async (doctype: string) => ({ data: state.metas[doctype] ?? null, children: [] })),
}));

import { toast } from "frappe-ui";
import { resetDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { setSession } from "@framework/ui/useSession";
import { resetUserRoles } from "@framework/ui/useUserRoles";
import { ActDenied, acts } from "@/acts/dispatcher";
import { openArgumentStep, paletteArgument, paletteOpen } from "@/shell/palette";
import { createRecordPage, SAVE_VETO, type RecordPageHost } from "../createRecordPage";
import { withRegisteringSource } from "@/pageEngine/context";
import { registerRecordPage, resetRegistry } from "../registry";
import type { AuthoredHandlers, HeaderItem, TabItem } from "../types";

const controllers: ReturnType<typeof createRecordPage>[] = [];

function makePage(overrides: Partial<RecordPageHost> = {}) {
  const host: RecordPageHost = {
    doctype: "CRM Lead",
    docname: "CRM-LEAD-1",
    doc: ref({ status: "Open" }),
    saved: ref({ status: "Open" }),
    meta: ref({ name: "CRM Lead", fields: [] }),
    perms: () => ({ read: 1, write: 1, delete: 0 }),
    isDirty: () => false,
    activeTab: () => "details",
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
  const controller = createRecordPage(host);
  controllers.push(controller);
  controller.header.provideBuiltins(() => [{ name: "save", label: "Save", run: () => {} }]);
  return { controller, page: controller.page };
}

function register(source: string, handlers: AuthoredHandlers) {
  return withRegisteringSource(source, async () => registerRecordPage("CRM Lead", handlers));
}

async function denial(promise: Promise<unknown>) {
  const error = (await promise.catch((rejected) => rejected)) as ActDenied;
  expect(error).toBeInstanceOf(ActDenied);
  return { act: error.act, reason: error.reason };
}

beforeEach(() => {
  resetRegistry();
  resetDoctypeMeta();
  resetUserRoles();
  state.metas = {};
  vi.spyOn(console, "warn").mockImplementation(() => {});
});

afterEach(() => {
  for (const controller of controllers.splice(0)) controller.leave();
  vi.restoreAllMocks();
});

describe("page.run", () => {
  it("runs a header item by its full name inside a hold, with the value", async () => {
    const run = vi.fn((page, value) => page.header.add({ name: "done", label: String(value) }));
    await register("crm", { onRefresh: (page) => page.header.add({ name: "convert", label: "Convert", run }) });
    const { controller, page } = makePage();
    await controller.refresh();

    await page.run("header.convert", "Deal");

    expect(run).toHaveBeenCalledWith(page, "Deal");
    expect(controller.header.visible().find((item) => item.name === "done")?.label).toBe("Deal");
  });

  it("rejects with missing for a name no surface holds, and for an item with no run", async () => {
    await register("crm", { onRefresh: (page) => page.header.add({ name: "help", label: "Help", href: "/help" }) });
    const { controller, page } = makePage();
    await controller.refresh();

    expect(await denial(page.run("header.nothing"))).toEqual({ act: "header.nothing", reason: "missing" });
    expect(await denial(page.run("header.help"))).toEqual({ act: "header.help", reason: "missing" });
    expect(await denial(page.run("nowhere.save"))).toEqual({ act: "nowhere.save", reason: "missing" });
  });

  it("finds an act added under an if in onRefresh only while the if holds", async () => {
    const run = vi.fn();
    await register("crm", {
      onRefresh: (page) => {
        if (page.doc.status === "Open") page.header.add({ name: "convert", label: "Convert", run });
      },
    });
    const doc = ref({ status: "Open" });
    const { controller, page } = makePage({ doc });
    await controller.refresh();
    await page.run("header.convert");
    expect(run).toHaveBeenCalledOnce();

    doc.value = { status: "Converted" };
    await controller.refresh();

    expect(await denial(page.run("header.convert"))).toMatchObject({ reason: "missing" });
    expect(run).toHaveBeenCalledOnce();
  });

  it("runs the later source's act when two sources add the same name", async () => {
    const first = vi.fn();
    const second = vi.fn();
    await register("crm", { onRefresh: (page) => page.header.add({ name: "convert", label: "Convert", run: first }) });
    await register("client-script:Lead", {
      onRefresh: (page) => page.header.add({ name: "convert", label: "Convert", run: second }),
    });
    const { controller, page } = makePage();
    await controller.refresh();

    await page.run("header.convert");

    expect(first).not.toHaveBeenCalled();
    expect(second).toHaveBeenCalledOnce();
  });

  it("rejects with hidden for a hidden act and for a member of a hidden container", async () => {
    const run = vi.fn();
    await register("crm", {
      onRefresh: (page) => {
        page.header.add([
          { name: "more", label: "More", display: "dropdown" },
          { name: "archive", label: "Archive", group: "more", run },
        ]);
        page.quickActions.add({ name: "call", label: "Call", run });
        page.quickActions.hide("call");
        page.header.hide("more");
      },
    });
    const { controller, page } = makePage();
    await controller.refresh();

    expect(await denial(page.run("quickActions.call"))).toMatchObject({ reason: "hidden" });
    expect(await denial(page.run("header.archive"))).toMatchObject({ reason: "hidden" });
    expect(await denial(page.run("header.more"))).toMatchObject({ reason: "missing" });
    expect(run).not.toHaveBeenCalled();
  });

  it("rejects with right when the page's doctype right is not held", async () => {
    const run = vi.fn();
    await register("crm", {
      onRefresh: (page) => {
        page.header.add({ name: "purge", label: "Purge", right: "delete", run });
        page.header.add({ name: "edit", label: "Edit", right: "write", run });
      },
    });
    const { controller, page } = makePage();
    await controller.refresh();

    expect(await denial(page.run("header.purge"))).toEqual({ act: "header.purge", reason: "right" });
    await page.run("header.edit");
    expect(run).toHaveBeenCalledOnce();
  });

  it("reads another doctype's right from its meta and the session roles", async () => {
    publishRoles(["Sales User"]);
    state.metas["CRM Deal"] = {
      name: "CRM Deal",
      permissions: [
        { role: "Sales User", permlevel: 0, read: 1, create: 1 },
        { role: "Sales User", permlevel: 1, read: 1, delete: 1 },
      ],
    };
    const run = vi.fn();
    await register("crm", {
      onRefresh: (page) => {
        page.header.add({ name: "convert", label: "Convert", right: { doctype: "CRM Deal", ptype: "create" }, run });
        page.header.add({ name: "drop", label: "Drop", right: { doctype: "CRM Deal", ptype: "delete" }, run });
      },
    });
    const { controller, page } = makePage();
    await controller.refresh();

    await page.run("header.convert");
    expect(run).toHaveBeenCalledOnce();
    expect(await denial(page.run("header.drop"))).toMatchObject({ reason: "right" });
  });

  it("runs a tab's create entry as tabs.<name>, hidden with its tab", async () => {
    const run = vi.fn();
    const calls: TabItem = { name: "calls", label: "Calls", create: { name: "log_call", label: "Log a call", icon: "lucide-phone", run } };
    await register("crm", {
      onRefresh: (page) => {
        page.tabs.add(calls);
        if (page.doc.status !== "Open") page.tabs.hide("calls");
      },
    });
    const doc = ref({ status: "Open" });
    const { controller, page } = makePage({ doc });
    await controller.refresh();
    await page.run("tabs.log_call");
    expect(run).toHaveBeenCalledWith(page, undefined);

    doc.value = { status: "Lost" };
    await controller.refresh();
    expect(await denial(page.run("tabs.log_call"))).toMatchObject({ reason: "hidden" });
  });

  it("rejects with what the act threw, and does nothing once the page has gone", async () => {
    const run = vi.fn(() => {
      throw new Error("No deal stage");
    });
    await register("crm", { onRefresh: (page) => page.header.add({ name: "convert", label: "Convert", run }) });
    const { controller, page } = makePage();
    await controller.refresh();

    await expect(page.run("header.convert")).rejects.toThrow("No deal stage");
    controller.leave();
    await expect(page.run("header.convert")).resolves.toBeUndefined();
    expect(run).toHaveBeenCalledOnce();
  });
});

describe("the acts available now", () => {
  it("lists each present, shown and allowed act with its fields", async () => {
    const options = vi.fn((page, query: string) => [{ value: query, label: page.docname }]);
    await register("crm", {
      onRefresh: (page) => {
        page.header.add({
          name: "assign",
          label: "Assign to",
          icon: "lucide-user",
          key: "Mod+Shift+A",
          argument: { label: "User", options },
          run: () => {},
        });
        page.header.add({ name: "quiet", label: "Quiet", palette: false, run: () => {} });
        page.header.add({ name: "purge", label: "Purge", right: "delete", run: () => {} });
        page.header.add({ name: "gone", label: "Gone", run: () => {} });
        page.header.hide("gone");
        page.header.add({ name: "link", label: "Link", href: "/x" });
      },
    });
    const { controller } = makePage();
    await controller.refresh();

    const listed = acts.available().filter((act) => act.name.startsWith("header."));
    expect(listed.map((act) => act.name)).toEqual(["header.save", "header.assign", "header.quiet"]);
    const assign = listed.find((act) => act.name === "header.assign")!;
    expect(assign).toMatchObject({ label: "Assign to", icon: "lucide-user", key: "Mod+Shift+A" });
    expect(await assign.argument!.options("ali")).toEqual([{ value: "ali", label: "CRM-LEAD-1" }]);
    expect(listed.find((act) => act.name === "header.quiet")?.palette).toBe(false);
  });

  it("takes a page's acts off when the page is left", async () => {
    await register("crm", { onRefresh: (page) => page.header.add({ name: "convert", label: "Convert", run: () => {} }) });
    const { controller } = makePage();
    await controller.refresh();
    expect(acts.available().some((act) => act.name === "header.convert")).toBe(true);

    controller.leave();

    expect(acts.available().some((act) => act.name.startsWith("header."))).toBe(false);
  });
});

describe("an act the reader asks for", () => {
  it("hands a failure to the host, and toasts a denial without running", async () => {
    const actFailed = vi.fn();
    const veto = Object.assign(new Error("Stage is required"), { name: SAVE_VETO });
    const item: HeaderItem = {
      name: "convert",
      label: "Convert",
      run: () => {
        throw veto;
      },
    };
    await register("crm", {
      onRefresh: (page) => page.header.add([item, { name: "purge", label: "Purge", right: "delete", run: () => {} }]),
    });
    const { controller } = makePage({ actFailed });
    await controller.refresh();

    await controller.perform("header.convert");
    await controller.perform("header.purge");

    expect(actFailed).toHaveBeenCalledExactlyOnceWith(veto);
    expect(toast.error).toHaveBeenCalledExactlyOnceWith("You do not have permission to do this");
  });

  it("opens the palette at the argument step of a clicked act that takes one, and runs it when given a value", async () => {
    const run = vi.fn();
    const assign: HeaderItem = {
      name: "assign",
      label: "Assign to…",
      argument: { label: "Users", options: () => [] },
      run,
    };
    await register("crm", { onRefresh: (page) => page.header.add([assign]) });
    const { controller } = makePage({ openArgument: openArgumentStep });
    await controller.refresh();

    await controller.perform("header.assign");
    expect(run).not.toHaveBeenCalled();
    expect(paletteOpen.value).toBe(true);
    expect(paletteArgument.value).toBe("header.assign");

    await controller.perform("header.assign", "sarah@example.com");
    expect(run).toHaveBeenCalledExactlyOnceWith(expect.anything(), "sarah@example.com");
    paletteOpen.value = false;
    paletteArgument.value = null;
  });
});

function publishRoles(roles: string[]) {
  const session: Session = {
    user: {
      name: "sales@example.com",
      full_name: "Sales",
      email: "sales@example.com",
      user_image: null,
      document_follow_notify: false,
    },
    roles,
    lang: "en",
    timezone: "Asia/Kolkata",
    defaults: {},
  };
  setSession(session);
}
