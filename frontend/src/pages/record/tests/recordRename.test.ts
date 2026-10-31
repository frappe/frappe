// `page.rename` on a mounted record page: the draft saves first, the server renames, the address follows.
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick } from "vue";
import { RouterView, type Router } from "vue-router";

vi.mock("@/shell/PageFrame.vue", async () => {
  const { defineComponent, h } = await import("vue");
  return {
    pageGutter: "px-[--page-gutter]",
    default: defineComponent({
      setup: (_, { slots }) => () => h("div", [h("header", slots.header?.()), slots.default?.()]),
    }),
  };
});

const script = vi.hoisted(() => ({ page: null as any, veto: "", renamedFromTitle: undefined as unknown }));

// Node cannot import a blob-URL module.
vi.mock("@/recordPage/evaluateClientScript", () => ({
  evaluateClientScript: async () => ({
    onRefresh: (page: any) => void (script.page = page),
    beforeSave: () => {
      if (script.veto) throw new Error(script.veto);
    },
    title: async (page: any) => {
      if (script.renamedFromTitle === null) script.renamedFromTitle = await page.rename(page.doc.title);
    },
  }),
}));

const discard = vi.hoisted(() => ({ asked: vi.fn(async () => false) }));
vi.mock("../discardChanges", () => ({ discardChanges: discard.asked }));

vi.mock("@/pages/List.vue", () => ({ default: { render: () => null } }));
vi.mock("@/shell/NotFound.vue", () => ({ default: { render: () => null } }));

const toasts = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }));
vi.mock("frappe-ui", async (original) => {
  const actual = await original<typeof import("frappe-ui")>();
  return { ...actual, toast: Object.assign(vi.fn(), actual.toast, toasts) };
});

import { clearDataCache } from "@framework/ui/cache";
import { resetDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { resetUserRoles } from "@framework/ui/useUserRoles";
import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { resetClientScripts } from "@/recordPage/clientScripts";
import { resetFormLayouts } from "@/recordPage/formLayoutSource/useFormLayout";
import { resetRegistry } from "@/recordPage/registry";
import { registerStandardPages } from "@/contributions/registry";
import { standardPages } from "@/pages/standardPages";
import { createShellRouter } from "@/router";
import { registerShell } from "@/router/routeFor";
import { resetViewMemory } from "../viewMemory";

registerStandardPages(standardPages);
// The router draws a page before its code is in; these tests start once it is.
await standardPages.record();

const RENAME = "/api/v2/method/frappe.client.rename_doc";
const GET_CLIENT_SCRIPTS = "frappe.custom.doctype.client_script.client_script.get_client_scripts";
const GET_FORM_LAYOUTS = "frappe.desk.doctype.form_layout.form_layout.get_form_layouts";
const META = {
  name: "Note",
  title_field: "title",
  allow_rename: 1,
  fields: [{ fieldname: "title", fieldtype: "Data", label: "Title" }],
};
const LAYOUT = [{ name: "details", label: "Details", sections: [{ columns: [{ fields: ["title"] }] }] }];

const server = {
  docs: {} as Record<string, Record<string, any>>,
  refusal: "",
  saveRefusal: "",
  renaming: null as Promise<void> | null,
  writes: [] as string[],
};

async function answer(url: URL, init?: RequestInit): Promise<[number, unknown]> {
  const path = decodeURIComponent(url.pathname);
  if (path === "/api/v2/doctype/Note/meta") return [200, { data: META }];
  if (path === `/api/v2/method/${GET_CLIENT_SCRIPTS}`)
    return [200, { data: { scripts: [{ name: "Note Script", script: "" }], can_write: false } }];
  if (path === `/api/v2/method/${GET_FORM_LAYOUTS}`) {
    if (url.searchParams.get("type") !== "Details") return [200, { data: { layouts: [], fallback: [] } }];
    return [200, { data: { layouts: [{ name: 1, condition: null, layout: LAYOUT }], fallback: LAYOUT } }];
  }
  if (path.endsWith("/activity")) return [200, { data: { activities: [], next: null } }];
  if (path === RENAME) {
    await server.renaming;
    return rename(JSON.parse(String(init!.body)));
  }
  const name = path.split("/").pop()!;
  if (init?.method === "PATCH") {
    server.writes.push(`save ${name}`);
    if (server.saveRefusal) return [417, { errors: [{ type: "ValidationError", message: server.saveRefusal }] }];
    server.docs[name] = { ...JSON.parse(String(init.body)), modified: "2026-10-31 11:00:00.000000" };
    return [200, { data: server.docs[name] }];
  }
  if (path.startsWith("/api/v2/document/Note/")) return [200, record(name)];
  return [200, { data: null }];
}

function rename(body: Record<string, any>): [number, unknown] {
  server.writes.push(`rename ${body.old_name} to ${body.new_name}${body.merge ? " merged" : ""}`);
  if (server.refusal) return [417, { errors: [{ type: "ValidationError", message: server.refusal }] }];
  server.docs[body.new_name] = { ...server.docs[body.old_name], name: body.new_name };
  delete server.docs[body.old_name];
  return [200, { data: body.new_name }];
}

function record(name: string) {
  return {
    data: { ...server.docs[name] },
    permissions: { read: 1, write: 1 },
    assignments: [],
    shares: [],
    tags: [],
    favourites: [],
    follows: false,
    users: {},
    link_titles: {},
    attachments: [],
    seen: [],
  };
}

const boot = {
  app: "frappe",
  shell_base: "/apps/frappe",
  prefixes: { frappe: { app: "frappe", modular: false } },
  session: { user: { name: "test@example.com", email: "test@example.com" } },
} as unknown as Boot;
const addresses = new Addresses({ doctypes: { Note: ["note", "desk"] }, modules: { desk: "Desk" } });
const socket = { on() {}, off() {}, emit() {} };
const apps: ReturnType<typeof createApp>[] = [];

beforeEach(() => {
  server.docs = { "N-1": { doctype: "Note", name: "N-1", title: "First", modified: "2026-10-31 10:00:00.000000" } };
  server.refusal = "";
  server.saveRefusal = "";
  server.renaming = null;
  server.writes = [];
  script.page = null;
  script.veto = "";
  script.renamedFromTitle = undefined;
  resetClientScripts();
  resetDoctypeMeta();
  resetFormLayouts();
  resetUserRoles();
  vi.spyOn(console, "warn").mockImplementation(() => {});
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string, init?: RequestInit) => {
      const [status, body] = await answer(new URL(String(input), "http://x"), init);
      return new Response(JSON.stringify(body), { status });
    }),
  );
});

afterEach(() => {
  for (const app of apps.splice(0)) app.unmount();
  document.body.innerHTML = "";
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  vi.clearAllMocks();
  resetRegistry();
  clearDataCache();
  resetViewMemory();
});

async function settle() {
  for (let turn = 0; turn < 10; turn++) {
    await nextTick();
    await new Promise((resolve) => setTimeout(resolve));
  }
}

async function mount(): Promise<{ root: HTMLElement; router: Router }> {
  const router = createShellRouter(boot, addresses);
  registerShell({ boot, addresses, router });
  await router.push("/note/N-1");
  const root = document.createElement("div");
  document.body.appendChild(root);
  const app = createApp(defineComponent({ render: () => h(RouterView) }));
  app.use(router);
  app.provide("boot", boot);
  app.provide("addresses", addresses);
  app.provide("socket", socket);
  app.mount(root);
  apps.push(app);
  await settle();
  return { root, router };
}

async function editTitle(root: HTMLElement, value: string) {
  const input = root.querySelector<HTMLInputElement>('.field[data-fieldname="title"] input')!;
  input.value = value;
  input.dispatchEvent(new Event("input"));
  input.dispatchEvent(new Event("change"));
  input.dispatchEvent(new Event("blur"));
  await settle();
}

async function renameTo(name: string, options?: { merge?: boolean }) {
  const renaming = script.page.rename(name, options);
  await settle();
  return renaming;
}

it("saves the dirty draft, renames, and opens the record at its new name with no question", async () => {
  const { root, router } = await mount();
  await editTitle(root, "Second");

  expect(await renameTo("N-2")).toBe("N-2");
  await settle();

  expect(server.writes).toEqual(["save N-1", "rename N-1 to N-2"]);
  expect(router.currentRoute.value.path).toBe("/note/N-2");
  expect(discard.asked).not.toHaveBeenCalled();
  expect(script.page.docname).toBe("N-2");
  expect(script.page.doc.title).toBe("Second");
  expect(toasts.success).toHaveBeenCalledWith("Renamed");
});

it("sends merge, and renames a clean record without saving it", async () => {
  server.docs["N-2"] = { doctype: "Note", name: "N-2", title: "Other", modified: "2026-10-31 10:00:00.000000" };
  const { router } = await mount();

  expect(await renameTo("N-2", { merge: true })).toBe("N-2");

  expect(server.writes).toEqual(["rename N-1 to N-2 merged"]);
  expect(router.currentRoute.value.path).toBe("/note/N-2");
});

it("stays on the record and resolves null with the server's reason when the rename is refused", async () => {
  server.refusal = "Another Note with name N-2 exists, select another name";
  const { router } = await mount();

  expect(await renameTo("N-2")).toBeNull();

  expect(router.currentRoute.value.path).toBe("/note/N-1");
  expect(toasts.error).toHaveBeenCalledWith("Another Note with name N-2 exists, select another name");
  expect(toasts.success).not.toHaveBeenCalled();
});

it("renames nothing when the draft's save is vetoed, and keeps the draft", async () => {
  script.veto = "Title needs a review";
  const { root, router } = await mount();
  await editTitle(root, "Second");

  expect(await renameTo("N-2")).toBeNull();

  expect(server.writes).toEqual([]);
  expect(router.currentRoute.value.path).toBe("/note/N-1");
  expect(script.page.doc.title).toBe("Second");
  expect(toasts.error).toHaveBeenCalledWith("Title needs a review");
});

it("renames from a field handler, to the value the reader just typed", async () => {
  script.renamedFromTitle = null;
  const { root, router } = await mount();

  await editTitle(root, "Renamed Note");
  await settle();

  expect(script.renamedFromTitle).toBe("Renamed Note");
  expect(server.writes).toEqual(["save N-1", "rename N-1 to Renamed Note"]);
  expect(router.currentRoute.value.path).toBe("/note/Renamed%20Note");
  expect(discard.asked).not.toHaveBeenCalled();
});

it("renames nothing when the server refuses the draft's save", async () => {
  server.saveRefusal = "Description is too long";
  const { root, router } = await mount();
  await editTitle(root, "Second");

  expect(await renameTo("N-2")).toBeNull();

  expect(server.writes).toEqual(["save N-1"]);
  expect(router.currentRoute.value.path).toBe("/note/N-1");
  expect(toasts.error).toHaveBeenCalledWith("Description is too long");
});

it("leaves the address alone when the reader moved on during the rename", async () => {
  let answer!: () => void;
  server.renaming = new Promise((resolve) => (answer = resolve));
  const { router } = await mount();

  const renaming = script.page.rename("N-2");
  await settle();
  await router.push("/note");
  answer();

  expect(await renaming).toBe("N-2");
  await settle();
  expect(router.currentRoute.value.path).toBe("/note");
  expect(toasts.success).not.toHaveBeenCalled();
});

it("names the new record when the reader keeps edits made during the rename", async () => {
  let answer!: () => void;
  server.renaming = new Promise((resolve) => (answer = resolve));
  const { root, router } = await mount();

  const renaming = script.page.rename("N-2");
  await settle();
  await editTitle(root, "Typed meanwhile");
  answer();

  expect(await renaming).toBe("N-2");
  expect(discard.asked).toHaveBeenCalledOnce();
  await settle();
  expect(router.currentRoute.value.path).toBe("/note/N-1");
  expect(toasts.error).toHaveBeenCalledWith("Renamed to N-2; this page still shows the old name");
  expect(toasts.success).not.toHaveBeenCalled();
});
