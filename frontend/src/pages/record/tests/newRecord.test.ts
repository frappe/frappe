// The full-page new record at `/<doctype>/new`: what it opens with, the insert its save sends,
// the leave warning, and what a script sees before and after the insert.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
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

const shown = vi.hoisted(() => ({
  confirms: [] as { title: string; onConfirm: () => Promise<void>; onCancel: () => Promise<void> }[],
  errors: [] as string[],
  events: [] as string[],
}));

vi.mock("frappe-ui", async (importOriginal) => ({
  ...(await importOriginal<typeof import("frappe-ui")>()),
  dialog: {
    confirm: (options: any) => {
      shown.confirms.push(options);
      return { close() {} };
    },
  },
  toast: {
    success() {},
    info() {},
    error: (message: string) => shown.errors.push(message),
  },
}));

// Node cannot import a blob-URL module.
vi.mock("@/recordPage/evaluateClientScript", () => ({
  evaluateClientScript: async () => ({
    onOpen: (page: any) => {
      shown.events.push(`onOpen isNew=${page.isNew}`);
      if (page.isNew) page.doc.priority = "High";
    },
    beforeSave: (page: any) => shown.events.push(`beforeSave isNew=${page.isNew}`),
    afterSave: (page: any) => shown.events.push(`afterSave isNew=${page.isNew} name=${page.doc.name}`),
  }),
}));

vi.mock("@/pages/Home.vue", () => ({ default: { render: () => null } }));
vi.mock("@/pages/List.vue", () => ({ default: { render: () => null } }));
vi.mock("@/pages/Module.vue", () => ({ default: { render: () => null } }));
vi.mock("@/shell/NotFound.vue", () => ({ default: { render: () => null } }));

import type { Session } from "@framework/ui/api";
import { clearDataCache } from "@framework/ui/cache";
import { resetDoctypeMeta } from "@framework/ui/composables/useDoctypeMeta";
import { resetSession, setSession } from "@framework/ui/composables/useSession";
import { resetUserRoles } from "@framework/ui/composables/useUserRoles";
import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { resetClientScripts } from "@/recordPage/clientScripts";
import { resetFormLayouts } from "@/recordPage/formLayoutSource/useFormLayout";
import { resetRegistry } from "@/recordPage/registry";
import { createShellRouter } from "@/router";
import { registerShell } from "@/router/routeFor";
import { resetViewMemory } from "../viewMemory";

const GET_CLIENT_SCRIPTS = "frappe.custom.doctype.client_script.client_script.get_client_scripts";
const GET_FORM_LAYOUTS = "frappe.desk.doctype.form_layout.form_layout.get_form_layouts";
const GET_NEW_DOC = "frappe.desk.form.load.get_new_doc";
const LAYOUT = [
  { name: "details", label: "Details", sections: [{ columns: [{ fields: ["title", "priority", "status"] }] }] },
];

const SESSION: Session = {
  user: { name: "test@example.com", full_name: "Test", email: "test@example.com", user_image: null, document_follow_notify: false },
  roles: ["Note Writer"],
  lang: "en",
  timezone: "Asia/Kolkata",
  defaults: {},
};

function noteMeta() {
  return {
    name: "Note",
    title_field: "title",
    autoname: "hash",
    fields: [
      { fieldname: "title", fieldtype: "Data", label: "Title" },
      { fieldname: "priority", fieldtype: "Data", label: "Priority" },
      { fieldname: "status", fieldtype: "Data", label: "Status" },
    ],
    permissions: [{ role: "Note Writer", permlevel: 0, read: 1, write: 1, create: 1 }],
  };
}

const server = {
  meta: noteMeta() as Record<string, any>,
  inserts: [] as Record<string, any>[],
  layoutTypes: [] as string[],
  rows: {} as Record<string, unknown[]>,
  newDocReads: 0,
  insertFails: false,
  defaultsHeld: null as Promise<void> | null,
  insertHeld: null as Promise<void> | null,
  updates: [] as Record<string, any>[],
};

async function answer(url: URL, init?: RequestInit): Promise<[unknown, number]> {
  const path = decodeURIComponent(url.pathname);
  if (path === "/api/v2/doctype/Note/meta") return [{ data: server.meta }, 200];
  if (path === `/api/v2/method/${GET_CLIENT_SCRIPTS}`)
    return [{ data: { scripts: [{ name: "Note Script", script: "" }], can_write: false } }, 200];
  if (path === `/api/v2/method/${GET_FORM_LAYOUTS}`) {
    const type = url.searchParams.get("type")!;
    server.layoutTypes.push(type);
    const layout = server.rows[type] ?? LAYOUT;
    return [{ data: { layouts: [{ name: 1, condition: null, layout }], fallback: LAYOUT } }, 200];
  }
  if (path === `/api/v2/method/${GET_NEW_DOC}`) {
    server.newDocReads++;
    await server.defaultsHeld;
    return [{ data: { doctype: "Note", name: "new-note-1", __islocal: 1, status: "Open" } }, 200];
  }
  if (init?.method === "POST" && path === "/api/v2/document/Note") {
    const body = JSON.parse(String(init.body));
    server.inserts.push(body);
    await server.insertHeld;
    if (server.insertFails)
      return [{ errors: [{ type: "ValidationError", message: "<b>Title</b> is taken" }] }, 417];
    return [{ data: { ...body, doctype: "Note", name: body.__newname ?? "NOTE-1", modified: "2026-10-23 10:00:00" } }, 200];
  }
  if (init?.method === "PATCH" && path === "/api/v2/document/Note/NOTE-1") {
    const body = JSON.parse(String(init.body));
    server.updates.push(body);
    return [{ data: { ...body, modified: "2026-10-23 10:05:00" } }, 200];
  }
  if (path.endsWith("/activity")) return [{ data: { activities: [], next: null } }, 200];
  if (path.startsWith("/api/v2/document/Note/"))
    return [
      {
        data: { doctype: "Note", name: path.split("/").pop(), modified: "2026-10-23 10:00:00" },
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
      },
      200,
    ];
  return [{ data: null }, 200];
}

const boot = {
  app: "frappe",
  shell_base: "/apps/frappe",
  prefixes: { frappe: { app: "frappe", modular: false } },
  session: { user: { name: "test@example.com", email: "test@example.com" } },
} as unknown as Boot;
const addresses = new Addresses({
  doctypes: { Note: ["note", "desk"], "Note Settings": ["note-settings", "desk"] },
  modules: { desk: "Desk" },
  singles: ["Note Settings"],
});
const socket = { on() {}, off() {}, emit() {} };
const apps: ReturnType<typeof createApp>[] = [];

beforeEach(() => {
  server.meta = noteMeta();
  server.inserts = [];
  server.layoutTypes = [];
  server.rows = {};
  server.newDocReads = 0;
  server.insertFails = false;
  server.defaultsHeld = null;
  server.insertHeld = null;
  server.updates = [];
  shown.confirms = [];
  shown.errors = [];
  shown.events = [];
  resetClientScripts();
  resetDoctypeMeta();
  resetFormLayouts();
  resetUserRoles();
  setSession(SESSION);
  vi.spyOn(console, "warn").mockImplementation(() => {});
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string, init?: RequestInit) => {
      const [body, status] = await answer(new URL(String(input), "http://x"), init);
      return new Response(JSON.stringify(body), { status });
    }),
  );
});

afterEach(() => {
  for (const app of apps.splice(0)) app.unmount();
  document.body.innerHTML = "";
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  resetRegistry();
  resetSession();
  clearDataCache();
  resetViewMemory();
});

async function settle() {
  for (let turn = 0; turn < 10; turn++) {
    await nextTick();
    await new Promise((resolve) => setTimeout(resolve));
  }
}

async function mount(address: string): Promise<{ root: HTMLElement; router: Router }> {
  const router = createShellRouter(boot, addresses);
  registerShell({ boot, addresses, router });
  await router.push(address);
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

function input(root: HTMLElement, fieldname: string) {
  return root.querySelector<HTMLInputElement>(`.field[data-fieldname="${fieldname}"] input`);
}

async function type(root: HTMLElement, fieldname: string, value: string) {
  const field = input(root, fieldname)!;
  field.value = value;
  field.dispatchEvent(new Event("input"));
  field.dispatchEvent(new Event("change"));
  field.dispatchEvent(new Event("blur"));
  await settle();
}

function saveButton(root: HTMLElement) {
  return [...root.querySelectorAll("button")].find((one) => one.textContent!.trim() === "Save")!;
}

async function save(root: HTMLElement) {
  saveButton(root).click();
  await settle();
}

function header(root: HTMLElement) {
  return root.querySelector("header")!.textContent!.replace(/\s+/g, " ");
}

describe("opening /<doctype>/new", () => {
  it("shows New {doctype}, a Not Saved mark and Save, with the server defaults under the query values", async () => {
    const { root } = await mount("/note/new?title=Hello&owner=intruder");

    expect(header(root)).toContain("New Note");
    expect(header(root)).toContain("Not Saved");
    expect(saveButton(root).disabled).toBe(false);
    expect(input(root, "title")!.value).toBe("Hello");
    expect(input(root, "status")!.value).toBe("Open");
    expect(server.layoutTypes).toContain("New Record");
    expect(server.layoutTypes).not.toContain("Side Panel");
  });

  it("draws no panel, activity, comment box, favourite or header menu", async () => {
    const { root } = await mount("/note/new");

    expect(root.querySelectorAll("[data-record-body] > *")).toHaveLength(1);
    expect(root.textContent).not.toContain("Activity");
    expect(root.querySelector('[aria-label="More actions"]')).toBeNull();
    expect(root.querySelector('[aria-label="Favourite"]')).toBeNull();
  });

  it("sends a single to its one record", async () => {
    const { router } = await mount("/note-settings/new");

    expect(router.currentRoute.value.name).toBe("record");
    expect(router.currentRoute.value.params.name).toBe("Note Settings");
  });

  it("says not permitted, and reads no defaults, without the create right", async () => {
    server.meta = { ...noteMeta(), permissions: [{ role: "Note Writer", permlevel: 0, read: 1 }] };

    const { root } = await mount("/note/new");

    expect(root.textContent).toContain("You do not have permission to create Note.");
    expect(input(root, "title")).toBeNull();
  });

  it("puts a name field at the top for a doctype named by prompt, filled from the query", async () => {
    server.meta = { ...noteMeta(), autoname: "Prompt" };

    const { root } = await mount("/note/new?__newname=My%20Note");

    const fieldnames = [...root.querySelectorAll(".field[data-fieldname]")].map(
      (field) => (field as HTMLElement).dataset.fieldname,
    );
    expect(fieldnames[0]).toBe("__newname");
    expect(input(root, "__newname")!.value).toBe("My Note");
  });
});

describe("inline fields", () => {
  const nickname = { fieldname: "nickname", fieldtype: "Data", label: "Nickname" };
  const visits = { fieldname: "visits", fieldtype: "Int", label: "Visits" };

  it("shows a New Record inline field, typed from the query, and inserts it", async () => {
    server.rows["New Record"] = [{ sections: [{ columns: [{ fields: ["title", visits] }] }] }];
    const { root } = await mount("/note/new?visits=3");

    expect(input(root, "visits")!.value).toBe("3");
    await save(root);

    expect(server.inserts[0]).toMatchObject({ visits: 3 });
  });

  it("keeps a value carried from a Quick Entry inline field the page does not show, and inserts it", async () => {
    server.rows["Quick Entry"] = [{ sections: [{ columns: [{ fields: ["title", nickname] }] }] }];
    const { root } = await mount("/note/new?title=Hello&nickname=Nick&owner=intruder");

    expect(input(root, "nickname")).toBeNull();
    await save(root);

    expect(server.inserts[0]).toMatchObject({ title: "Hello", nickname: "Nick" });
    expect(server.inserts[0]).not.toHaveProperty("owner");
  });

  it("reads no Quick Entry rows when the address carries no values", async () => {
    await mount("/note/new");

    expect(server.layoutTypes).not.toContain("Quick Entry");
  });
});

describe("saving the new record", () => {
  it("inserts the draft, then replaces the address with the saved record's", async () => {
    const { root, router } = await mount("/note/new?status=Closed");
    await type(root, "title", "Hello");

    await save(root);

    expect(server.inserts).toEqual([{ title: "Hello", priority: "High", status: "Closed" }]);
    expect(router.currentRoute.value.fullPath).toBe("/note/NOTE-1");
    expect(window.history.state.replaced).toBe(true);
  });

  it("inserts with no typed changes", async () => {
    const { root, router } = await mount("/note/new?title=Prefilled");

    await save(root);

    expect(server.inserts).toHaveLength(1);
    expect(router.currentRoute.value.fullPath).toBe("/note/NOTE-1");
  });

  it("sends a prompt name as __newname, never name", async () => {
    server.meta = { ...noteMeta(), autoname: "Prompt" };
    const { root, router } = await mount("/note/new");
    await type(root, "__newname", "My Note");

    await save(root);

    expect(server.inserts[0].__newname).toBe("My Note");
    expect(server.inserts[0]).not.toHaveProperty("name");
    expect(router.currentRoute.value.fullPath).toBe("/note/My%20Note");
  });

  it("saves on Ctrl+S", async () => {
    const { router } = await mount("/note/new?title=Hello");

    window.dispatchEvent(new KeyboardEvent("keydown", { key: "s", ctrlKey: true }));
    await settle();

    expect(server.inserts).toHaveLength(1);
    expect(router.currentRoute.value.fullPath).toBe("/note/NOTE-1");
  });

  it("inserts once when the move to the saved record is refused, and a second save only moves", async () => {
    const { root, router } = await mount("/note/new?title=Hello");
    let refuse = true;
    router.beforeEach((to) => !(refuse && to.name === "record"));

    await save(root);
    expect(router.currentRoute.value.fullPath).toBe("/note/new?title=Hello");

    refuse = false;
    await save(root);

    expect(server.inserts).toHaveLength(1);
    expect(router.currentRoute.value.fullPath).toBe("/note/NOTE-1");
    expect(shown.events.filter((event) => event.startsWith("afterSave"))).toHaveLength(1);
    expect(shown.events.filter((event) => event.startsWith("beforeSave"))).toHaveLength(1);
  });

  it("locks the form while the insert runs, and takes the server's reply as the draft", async () => {
    let release!: () => void;
    server.insertHeld = new Promise((resolve) => (release = resolve));
    const { root, router } = await mount("/note/new?title=Hello");

    saveButton(root).click();
    await settle();
    expect(root.querySelector("[data-record-form]")!.hasAttribute("inert")).toBe(true);
    release();
    await settle();

    expect(router.currentRoute.value.fullPath).toBe("/note/NOTE-1");
    expect(server.inserts).toHaveLength(1);
  });

  it("saves in place when the person edits after a refused move to the saved record", async () => {
    const { root, router } = await mount("/note/new?title=Hello");
    let refuse = true;
    router.beforeEach((to) => !(refuse && to.name === "record"));
    await save(root);
    expect(root.querySelector("[data-record-form]")!.hasAttribute("inert")).toBe(false);

    await type(root, "status", "Edited after the insert");
    refuse = false;
    await save(root);

    expect(server.inserts).toHaveLength(1);
    expect(server.updates).toHaveLength(1);
    expect(server.updates[0]).toMatchObject({ name: "NOTE-1", status: "Edited after the insert", modified: "2026-10-23 10:00:00" });
    expect(router.currentRoute.value.fullPath).toBe("/note/NOTE-1");
  });

  it("keeps the page, the values and the server message as text when the insert fails", async () => {
    server.insertFails = true;
    const { root, router } = await mount("/note/new");
    await type(root, "title", "Taken");

    await save(root);

    expect(router.currentRoute.value.fullPath).toBe("/note/new");
    expect(input(root, "title")!.value).toBe("Taken");
    expect(shown.errors).toEqual(["Title is taken"]);
    expect(header(root)).toContain("Not Saved");
  });
});

describe("an opening that ends early", () => {
  it("runs no script for a page left before its defaults arrived", async () => {
    let release!: () => void;
    server.defaultsHeld = new Promise((resolve) => (release = resolve));
    const { router } = await mount("/note/new");

    await router.push("/note");
    release();
    await settle();

    expect(shown.events).toEqual([]);
  });
});

describe("a client script", () => {
  it("sees page.isNew true on open and around the insert, then false on the saved record's open", async () => {
    const { root } = await mount("/note/new?title=Hello");

    expect(shown.events).toEqual(["onOpen isNew=true"]);
    expect(input(root, "priority")!.value).toBe("High");

    await save(root);

    expect(shown.events).toEqual([
      "onOpen isNew=true",
      "beforeSave isNew=true",
      "afterSave isNew=false name=NOTE-1",
      "onOpen isNew=false",
    ]);
  });
});

describe("leaving with typed values", () => {
  it("leaves at once when nothing was typed, though onOpen set a value", async () => {
    const { router } = await mount("/note/new");

    await router.push("/note");
    await settle();

    expect(shown.confirms).toEqual([]);
    expect(router.currentRoute.value.fullPath).toBe("/note");
  });

  it("asks before Back, and stays when the person keeps editing", async () => {
    const { root, router } = await mount("/note/new");
    await type(root, "title", "Draft");

    void router.push("/note");
    await settle();

    expect(shown.confirms.map((one) => one.title)).toEqual(["Discard unsaved changes?"]);
    await shown.confirms[0].onCancel();
    await settle();
    expect(router.currentRoute.value.fullPath).toBe("/note/new");
    expect(input(root, "title")!.value).toBe("Draft");
  });

  it("asks before a query change, then builds the record again from the new query", async () => {
    const { root, router } = await mount("/note/new?title=First");
    await type(root, "title", "Typed");

    void router.push("/note/new?title=Second");
    await settle();
    expect(shown.confirms).toHaveLength(1);
    await shown.confirms[0].onConfirm();
    await settle();

    expect(router.currentRoute.value.fullPath).toBe("/note/new?title=Second");
    expect(input(root, "title")!.value).toBe("Second");
    expect(server.newDocReads).toBe(2);
  });

  it("keeps the draft and asks nothing on a change of the hash alone", async () => {
    const { root, router } = await mount("/note/new?title=First");
    await type(root, "title", "Typed");

    await router.push("/note/new?title=First#notes");
    await settle();

    expect(shown.confirms).toEqual([]);
    expect(router.currentRoute.value.hash).toBe("#notes");
    expect(input(root, "title")!.value).toBe("Typed");
    expect(server.newDocReads).toBe(1);
  });

  it("asks the browser before a reload or a tab close", async () => {
    const { root } = await mount("/note/new");
    const before = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(before);
    expect(before.defaultPrevented).toBe(false);

    await type(root, "title", "Draft");
    const after = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(after);

    expect(after.defaultPrevented).toBe(true);
  });

  it("builds the record again on a reload, from the defaults and the query", async () => {
    const first = await mount("/note/new?title=Hello");
    await type(first.root, "title", "Typed");
    for (const app of apps.splice(0)) app.unmount();
    document.body.innerHTML = "";

    const { root } = await mount("/note/new?title=Hello");

    expect(input(root, "title")!.value).toBe("Hello");
    expect(input(root, "status")!.value).toBe("Open");
  });
});
