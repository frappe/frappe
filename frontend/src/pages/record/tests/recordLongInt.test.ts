// A Long Int past 2^53 loads exact, and a save of another field sends its digits back unchanged.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick } from "vue";
import { RouterView } from "vue-router";

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

const BIG = "9007199254740993";
const GET_CLIENT_SCRIPTS = "frappe.custom.doctype.client_script.client_script.get_client_scripts";
const GET_FORM_LAYOUTS = "frappe.desk.doctype.form_layout.form_layout.get_form_layouts";
const META = {
  name: "Note",
  title_field: "title",
  fields: [
    { fieldname: "title", fieldtype: "Data", label: "Title" },
    { fieldname: "views", fieldtype: "Long Int", label: "Views" },
  ],
};
const LAYOUT = [
  { name: "details", label: "Details", sections: [{ columns: [{ fields: ["title", "views"] }] }] },
];
const PARTS = {
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

const sent: { patch?: string } = {};

// The record reply is written by hand, so its Long Int is a JSON number with all its digits.
function answer(url: URL, init?: RequestInit): string {
  const path = decodeURIComponent(url.pathname);
  if (path === "/api/v2/doctype/Note/meta") return JSON.stringify({ data: META });
  if (path === `/api/v2/method/${GET_CLIENT_SCRIPTS}`)
    return JSON.stringify({ data: { scripts: [], can_write: false } });
  if (path === `/api/v2/method/${GET_FORM_LAYOUTS}`) {
    if (url.searchParams.get("type") !== "Details") return JSON.stringify({ data: { layouts: [], fallback: [] } });
    return JSON.stringify({ data: { layouts: [{ name: 1, condition: null, layout: LAYOUT }], fallback: LAYOUT } });
  }
  if (path.endsWith("/activity")) return JSON.stringify({ data: { activities: [], next: null } });
  if (init?.method === "PATCH") {
    sent.patch = String(init.body);
    return JSON.stringify({ data: { ...JSON.parse(sent.patch), modified: "2026-10-24 11:00:00.000000" } });
  }
  if (path.startsWith("/api/v2/document/Note/")) {
    const doc = '{"doctype":"Note","name":"N-1","title":"First","modified":"2026-10-24 10:00:00.000000",'
      + `"views":${BIG}}`;
    return `{"data":${doc},${JSON.stringify(PARTS).slice(1)}`;
  }
  return JSON.stringify({ data: null });
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
  delete sent.patch;
  resetClientScripts();
  resetDoctypeMeta();
  resetFormLayouts();
  resetUserRoles();
  vi.spyOn(console, "warn").mockImplementation(() => {});
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string, init?: RequestInit) => {
      return new Response(answer(new URL(String(input), "http://x"), init), { status: 200 });
    }),
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

async function mount() {
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
  return root;
}

function input(root: HTMLElement, fieldname: string) {
  return root.querySelector<HTMLInputElement>(`.field[data-fieldname="${fieldname}"] input`)!;
}

async function editTitle(root: HTMLElement, value: string) {
  const title = input(root, "title");
  title.value = value;
  title.dispatchEvent(new Event("input"));
  title.dispatchEvent(new Event("change"));
  title.dispatchEvent(new Event("blur"));
  await settle();
}

describe("a Long Int past 2^53 on the record page", () => {
  it("shows its digits, and a save of another field sends them back unchanged", async () => {
    const root = await mount();
    expect(input(root, "views").value).toBe(BIG);

    await editTitle(root, "Second");
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "s", ctrlKey: true }));
    await settle();

    expect(sent.patch).toBeDefined();
    expect(JSON.parse(sent.patch!)).toMatchObject({ title: "Second", views: BIG });
  });
});
