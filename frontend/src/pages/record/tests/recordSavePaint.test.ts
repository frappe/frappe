// Ctrl+S and the Save button each paint the page once, and Save spins until `afterSave` ends.
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

const hooks = vi.hoisted(() => ({ afterSave: Promise.resolve() }));

// Node cannot import a blob-URL module.
vi.mock("@/recordPage/evaluateClientScript", () => ({
  evaluateClientScript: async () => ({
    onRefresh: (page: any) => page.quickActions.add({ name: "title", label: `title|${page.doc.title}` }),
    beforeSave: (page: any) => page.quickActions.add({ name: "before", label: "before|" }),
    afterSave: async (page: any) => {
      await hooks.afterSave;
      page.quickActions.add({ name: "after", label: "after|" });
    },
  }),
}));

vi.mock("@/pages/Home.vue", () => ({ default: { render: () => null } }));
vi.mock("@/pages/List.vue", () => ({ default: { render: () => null } }));
vi.mock("@/pages/Module.vue", () => ({ default: { render: () => null } }));
vi.mock("@/shell/NotFound.vue", () => ({ default: { render: () => null } }));

import { clearDataCache } from "@framework/ui/cache";
import { resetDoctypeMeta } from "@framework/ui/composables/useDoctypeMeta";
import { resetUserRoles } from "@framework/ui/composables/useUserRoles";
import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { resetClientScripts } from "@/recordPage/clientScripts";
import { resetFormLayouts } from "@/recordPage/formLayoutSource/useFormLayout";
import { resetRegistry } from "@/recordPage/registry";
import { createShellRouter } from "@/router";
import { registerShell } from "@/router/routeFor";
import { resetViewMemory } from "../viewMemory";

const OLD = "2026-09-25 10:00:00.000000";
const NEW = "2026-09-25 11:00:00.000000";
const GET_CLIENT_SCRIPTS = "frappe.custom.doctype.client_script.client_script.get_client_scripts";
const GET_FORM_LAYOUTS = "frappe.desk.doctype.form_layout.form_layout.get_form_layouts";
const META = {
  name: "Note",
  title_field: "title",
  fields: [{ fieldname: "title", fieldtype: "Data", label: "Title" }],
};
const LAYOUT = [{ name: "details", label: "Details", sections: [{ columns: [{ fields: ["title"] }] }] }];

function gate() {
  let open!: () => void;
  const opened = new Promise<void>((resolve) => (open = resolve));
  return { opened, open };
}

const server = { doc: {} as Record<string, any>, write: gate(), afterSave: gate() };

async function answer(url: URL, init?: RequestInit): Promise<unknown> {
  const path = decodeURIComponent(url.pathname);
  if (path === "/api/v2/doctype/Note/meta") return { data: META };
  if (path === `/api/v2/method/${GET_CLIENT_SCRIPTS}`)
    return { data: { scripts: [{ name: "Note Script", script: "" }], can_write: false } };
  if (path === `/api/v2/method/${GET_FORM_LAYOUTS}`) {
    if (url.searchParams.get("type") !== "Details") return { data: { layouts: [], fallback: [] } };
    return { data: { layouts: [{ name: 1, condition: null, layout: LAYOUT }], fallback: LAYOUT } };
  }
  if (path.endsWith("/activity")) return { data: { activities: [], next: null } };
  if (init?.method === "PATCH") {
    await server.write.opened;
    server.doc = { ...JSON.parse(String(init.body)), modified: NEW };
    return { data: server.doc };
  }
  if (path.startsWith("/api/v2/document/Note/"))
    return {
      data: { ...server.doc },
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
  return { data: null };
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
  server.doc = { doctype: "Note", name: "N-1", title: "First", modified: OLD };
  server.write = gate();
  server.afterSave = gate();
  hooks.afterSave = server.afterSave.opened;
  resetClientScripts();
  resetDoctypeMeta();
  resetFormLayouts();
  resetUserRoles();
  vi.spyOn(console, "warn").mockImplementation(() => {});
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string, init?: RequestInit) => {
      const body = await answer(new URL(String(input), "http://x"), init);
      return new Response(JSON.stringify(body), { status: 200 });
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

function drawn(root: HTMLElement) {
  return [...root.querySelectorAll("button")]
    .map((button) => button.textContent!.trim())
    .filter((text) => text.includes("|"))
    .join(" ");
}

function watchPaints(root: HTMLElement) {
  const seen = [drawn(root)];
  const observer = new MutationObserver(() => {
    if (drawn(root) !== seen.at(-1)) seen.push(drawn(root));
  });
  observer.observe(root, { childList: true, subtree: true, characterData: true });
  return { seen, stop: () => observer.disconnect() };
}

function saveButton(root: HTMLElement) {
  return [...root.querySelectorAll("button")].find((one) => one.textContent!.trim() === "Save")!;
}

function spins(root: HTMLElement) {
  return saveButton(root).querySelector('[aria-label="Loading"]') !== null;
}

async function editTitle(root: HTMLElement, value: string) {
  const input = root.querySelector<HTMLInputElement>('.field[data-fieldname="title"] input')!;
  input.value = value;
  input.dispatchEvent(new Event("input"));
  input.dispatchEvent(new Event("change"));
  input.dispatchEvent(new Event("blur"));
  await settle();
}

describe.each([
  ["Ctrl+S", () => window.dispatchEvent(new KeyboardEvent("keydown", { key: "s", ctrlKey: true }))],
  ["the Save button", (root: HTMLElement) => saveButton(root).click()],
])("a save from %s", (_, press: (root: HTMLElement) => void) => {
  it("paints once, after afterSave, and the Save button spins until afterSave settles", async () => {
    const root = await mount();
    await editTitle(root, "Second");
    expect(drawn(root)).toBe("title|First");
    expect(spins(root)).toBe(false);
    const paints = watchPaints(root);

    press(root);
    await settle();
    expect(spins(root)).toBe(true);
    expect(drawn(root)).toBe("title|First");
    server.write.open();
    await settle();
    expect(spins(root)).toBe(true);
    expect(drawn(root)).toBe("title|First");
    server.afterSave.open();
    await settle();

    expect(spins(root)).toBe(false);
    expect(paints.seen).toEqual(["title|First", "title|Second after|"]);
    paints.stop();
  });
});
