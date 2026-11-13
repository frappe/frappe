// A saved record's "Edit layout" row and "Edit panel" link: the layout the record shows, for a manager only, with no request of their own.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick } from "vue";
import { RouterView, type Router } from "vue-router";

vi.mock("@/shell/PageFrame.vue", async () => {
  const { defineComponent, h } = await import("vue");
  return {
    pageGutter: "px-[--page-gutter]",
    default: defineComponent({
      setup: (_, { slots }) => () => h("div", [h("header", slots.header?.()), slots.default?.(), slots.panel?.({})]),
    }),
  };
});

vi.mock("@/pages/List.vue", () => ({ default: { render: () => null } }));
vi.mock("@/shell/NotFound.vue", () => ({ default: { render: () => null } }));

import { clearDataCache } from "@framework/ui/cache";
import { resetDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { resetUserRoles } from "@framework/ui/useUserRoles";
import { setSession } from "@framework/ui/useSession";
import { acts } from "@/acts/dispatcher";
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
await standardPages.record();

const GET_FORM_LAYOUTS = "frappe.desk.doctype.form_layout.form_layout.get_form_layouts";
const META = {
  name: "Salutation",
  fields: [
    { fieldname: "salutation", fieldtype: "Data", label: "Salutation" },
    { fieldname: "vip", fieldtype: "Check", label: "VIP" },
  ],
};
const LAYOUT = [{ name: "details", label: "Details", sections: [{ columns: [{ fields: ["salutation", "vip"] }] }] }];
const DETAILS = [
  { name: "FL-1", title: "VIP", condition: "doc.vip", layout: LAYOUT },
  { name: "FL-2", condition: null, layout: LAYOUT },
];

const fetched: string[] = [];
let vip = 1;

async function answer(url: URL): Promise<[number, unknown]> {
  const path = decodeURIComponent(url.pathname);
  if (path === "/api/v2/doctype/Salutation/meta") return [200, { data: META }];
  if (path === `/api/v2/method/${GET_FORM_LAYOUTS}`) {
    if (url.searchParams.get("type") !== "Details") return [200, { data: { layouts: [], fallback: [] } }];
    return [200, { data: { layouts: DETAILS, fallback: LAYOUT } }];
  }
  if (path.endsWith("/activity")) return [200, { data: { activities: [], next: null } }];
  if (path === "/api/v2/document/Salutation/Mr") return [200, record()];
  return [200, { data: null }];
}

function record() {
  const doc = { doctype: "Salutation", name: "Mr", salutation: "Mr", vip, modified: "2026-10-31 10:00:00.000000" };
  return { data: doc, permissions: { read: 1, write: 1 }, assignments: [], shares: [], tags: [], favourites: [], follows: false };
}

const session = { user: { name: "test@example.com", email: "test@example.com" }, roles: [] as string[] };
const boot = {
  app: "frappe",
  shell_base: "/apps/frappe",
  prefixes: { frappe: { app: "frappe", modular: false } },
  developer_mode: false,
  session,
} as unknown as Boot;
const addresses = new Addresses({
  doctypes: { Salutation: ["salutation", "desk"], DocType: ["doctype", "core"] },
  modules: { desk: "Desk", core: "Core" },
});
const apps: ReturnType<typeof createApp>[] = [];

beforeEach(() => {
  fetched.length = 0;
  vip = 1;
  session.roles = [];
  resetClientScripts();
  resetDoctypeMeta();
  resetFormLayouts();
  resetUserRoles();
  setSession(session as any);
  vi.spyOn(console, "warn").mockImplementation(() => {});
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string) => {
      const url = new URL(String(input), "http://x");
      fetched.push(`${url.pathname}?${url.searchParams.get("type") ?? ""}`);
      const [status, body] = await answer(url);
      return new Response(JSON.stringify(body), { status });
    })
  );
});

afterEach(() => {
  for (const app of apps.splice(0)) app.unmount();
  document.body.innerHTML = "";
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
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
  await router.push("/salutation/Mr");
  const root = document.createElement("div");
  document.body.appendChild(root);
  const app = createApp(defineComponent({ render: () => h(RouterView) }));
  app.use(router);
  app.provide("boot", boot);
  app.provide("addresses", addresses);
  app.provide("socket", { on() {}, off() {}, emit() {} });
  app.mount(root);
  apps.push(app);
  await settle();
  return { root, router };
}

const editPanel = (root: HTMLElement) =>
  [...root.querySelectorAll("a")].find((one) => one.textContent?.trim() === "Edit panel");

describe("a manager on a saved record", () => {
  beforeEach(() => (session.roles = ["System Manager"]));

  it("opens the editor at the conditional Details layout the record shows", async () => {
    const { router } = await mount();
    const push = vi.spyOn(router, "push").mockResolvedValue(undefined);

    await acts.run("header.edit_layout");

    const query = { mode: "customize", layout: "details", row: "FL-1" };
    expect(push).toHaveBeenCalledWith({ name: "doctype-editor", params: { name: "Salutation" }, query });
  });

  it("names no row when the default Details layout shows", async () => {
    vip = 0;
    const { router } = await mount();
    const push = vi.spyOn(router, "push").mockResolvedValue(undefined);

    await acts.run("header.edit_layout");

    expect(push).toHaveBeenCalledWith(expect.objectContaining({ query: { mode: "customize", layout: "details" } }));
  });

  it("links the panel to the editor's side panel", async () => {
    const { root } = await mount();

    expect(editPanel(root)?.getAttribute("href")).toBe("/apps/frappe/doctype/Salutation?mode=customize&layout=side-panel");
  });
});

describe("a person without the right", () => {
  it("gets neither entry, and the page reads exactly what a manager's does", async () => {
    const { root } = await mount();
    const reads = [...fetched].sort();
    expect(acts.find("header.edit_layout")).toBeUndefined();
    expect(editPanel(root)).toBeUndefined();

    for (const app of apps.splice(0)) app.unmount();
    resetDoctypeMeta();
    resetFormLayouts();
    clearDataCache();
    fetched.length = 0;
    session.roles = ["System Manager"];
    await mount();

    expect(acts.find("header.edit_layout")).toBeDefined();
    expect([...fetched].sort()).toEqual(reads);
  });
});
