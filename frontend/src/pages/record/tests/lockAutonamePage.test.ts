// A mounted saved record shows its `field:` autoname field read-only.
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

const GET_CLIENT_SCRIPTS = "frappe.custom.doctype.client_script.client_script.get_client_scripts";
const GET_FORM_LAYOUTS = "frappe.desk.doctype.form_layout.form_layout.get_form_layouts";
const META = {
  name: "Salutation",
  autoname: "field:salutation",
  allow_rename: 1,
  fields: [
    { fieldname: "salutation", fieldtype: "Data", label: "Salutation", reqd: 1, unique: 1 },
    { fieldname: "note", fieldtype: "Data", label: "Salutation" },
  ],
};
const LAYOUT = [{ name: "details", label: "Details", sections: [{ columns: [{ fields: ["salutation", "note"] }] }] }];

const server = {
  docs: {} as Record<string, Record<string, any>>,
};

async function answer(url: URL): Promise<[number, unknown]> {
  const path = decodeURIComponent(url.pathname);
  if (path === "/api/v2/doctype/Salutation/meta") return [200, { data: META }];
  if (path === `/api/v2/method/${GET_CLIENT_SCRIPTS}`)
    return [200, { data: { scripts: [], can_write: false } }];
  if (path === `/api/v2/method/${GET_FORM_LAYOUTS}`) {
    if (url.searchParams.get("type") !== "Details") return [200, { data: { layouts: [], fallback: [] } }];
    return [200, { data: { layouts: [{ name: 1, condition: null, layout: LAYOUT }], fallback: LAYOUT } }];
  }
  if (path.endsWith("/activity")) return [200, { data: { activities: [], next: null } }];
  const name = path.split("/").pop()!;
  if (path.startsWith("/api/v2/document/Salutation/")) return [200, record(name)];
  return [200, { data: null }];
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
    link_marks: {},
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
const addresses = new Addresses({ doctypes: { Salutation: ["salutation", "desk"] }, modules: { desk: "Desk" } });
const socket = { on() {}, off() {}, emit() {} };
const apps: ReturnType<typeof createApp>[] = [];

beforeEach(() => {
  server.docs = { Mr: { doctype: "Salutation", name: "Mr", salutation: "Mr", note: "", modified: "2026-10-31 10:00:00.000000" } };
  resetClientScripts();
  resetDoctypeMeta();
  resetFormLayouts();
  resetUserRoles();
  vi.spyOn(console, "warn").mockImplementation(() => {});
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string) => {
      const [status, body] = await answer(new URL(String(input), "http://x"));
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

async function mount(path = "/salutation/Mr"): Promise<{ root: HTMLElement; router: Router }> {
  const router = createShellRouter(boot, addresses);
  registerShell({ boot, addresses, router });
  await router.push(path);
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

const field = (root: HTMLElement, fieldname: string) => root.querySelector(`.field[data-fieldname="${fieldname}"]`)!;

it("reads the autoname field of a saved record only and leaves the others editable", async () => {
  const { root } = await mount();
  expect(field(root, "salutation").querySelector("input")).toBeNull();
  expect(field(root, "salutation").querySelector('[data-slot="read-value"]')?.textContent).toBe("Mr");
  expect(field(root, "note").querySelector("input")).not.toBeNull();
});
