// `page.activity` as executable claims: the server's rows and a script's own in one
// time order, a scroll held until the replay commits, and `types` staged like any op.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ref, watch } from "vue";

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

import { createRecordPage, type RecordPageHost } from "../createRecordPage";
import { registerRecordPage, resetRegistry } from "../registry";
import type { ActivityRow } from "../types";

const CallRow = { render: () => null };

const ROWS: ActivityRow[] = [
  {
    type: "comment",
    key: "comment:c1",
    timestamp: "2026-09-23 09:00:00",
    author: { email: "a@example.com", fullname: "A", image: "" },
    data: { content: "first" },
  },
  {
    type: "version",
    key: "version:v1-0",
    timestamp: "2026-09-23 10:00:00",
    author: { email: "b@example.com", fullname: "B", image: "" },
    data: { field: "status" },
  },
  {
    type: "comment",
    key: "comment:c2",
    timestamp: "2026-09-23 11:00:00",
    author: { email: "a@example.com", fullname: "A", image: "" },
    data: { content: "last" },
  },
];

/** The host's feed half, recorded, not performed. */
function makePage(overrides: Partial<RecordPageHost> = {}) {
  const rows = ref<ActivityRow[]>([...ROWS]);
  const scrolled: string[] = [];
  const reloads: string[] = [];
  const host: RecordPageHost = {
    doctype: "CRM Deal",
    docname: "CRM-DEAL-1",
    doc: ref({}),
    saved: ref({}),
    meta: ref(null),
    perms: () => ({}),
    isDirty: () => false,
    activeTab: () => "details",
    activateTab: () => {},
    save: async () => {},
    reload: async () => {},
    router: {} as any,
    activityRows: () => rows.value,
    scrollToActivity: async (key) => {
      scrolled.push(key);
      return true;
    },
    reloadActivity: async () => void reloads.push("activity"),
    fileRows: () => [],
    reloadFiles: async () => {},
    ...overrides,
  };
  const controller = createRecordPage(host);
  return { controller, page: controller.page, rows, scrolled, reloads };
}

const names = (items: readonly { name: string }[]) => items.map((item) => item.name);

let warnings: string[];

beforeEach(() => {
  resetRegistry();
  warnings = [];
  vi.spyOn(console, "warn").mockImplementation((message: string) => void warnings.push(message));
});

afterEach(() => vi.restoreAllMocks());

describe("the list a script reads", () => {
  it("hands each server row back under its key, oldest first", () => {
    const { page } = makePage();

    expect(page.activity.items[0]).toEqual({
      name: "comment:c1",
      type: "comment",
      timestamp: "2026-09-23 09:00:00",
      author: { email: "a@example.com", fullname: "A", image: "" },
      data: { content: "first" },
    });
    expect(names(page.activity.items)).toEqual(["comment:c1", "version:v1-0", "comment:c2"]);
  });

  it("marks a row the server has not answered yet", () => {
    const { page, rows } = makePage();
    rows.value.push({ type: "comment", key: "pending:7", pending: true, data: {} });

    const pending = page.activity.items.find((item) => item.name === "pending:7");
    expect(pending).toMatchObject({ pending: true });
  });

  it("places a script's row by its timestamp among the server's rows", () => {
    const { page } = makePage();

    page.activity.add({
      name: "call:17",
      timestamp: "2026-09-23 10:15:00",
      component: CallRow,
      props: { id: 17 },
    });

    expect(names(page.activity.items)).toEqual([
      "comment:c1",
      "version:v1-0",
      "call:17",
      "comment:c2",
    ]);
  });

  it("breaks a tie on the timestamp by name, as the server does", () => {
    const { page } = makePage();

    page.activity.add({ name: "a:1", timestamp: "2026-09-23 10:00:00", component: CallRow });

    expect(names(page.activity.items).slice(1, 3)).toEqual(["a:1", "version:v1-0"]);
  });

  it("orders rows in the same millisecond by the time's text, then the name by code unit", () => {
    const { page, rows } = makePage();
    const at = "2026-09-23 10:00:00.123";
    rows.value.push({ ...ROWS[0], key: "comment:a", timestamp: `${at}900` });
    rows.value.push({ ...ROWS[0], key: "comment:Z", timestamp: `${at}900` });
    page.activity.add({ name: "call:1", timestamp: `${at}400`, component: CallRow });

    expect(names(page.activity.items).slice(2, 5)).toEqual(["call:1", "comment:Z", "comment:a"]);
  });

  it("refuses a write to the list, naming the verb that adds a row", () => {
    const { page } = makePage();
    vi.spyOn(console, "error").mockImplementation(() => {});

    expect(() => ((page.activity.items[0] as any).type = "email")).toThrow(
      "page.activity.add(...)",
    );
  });

  it("answers `has` for a loaded server row and for a script's own", () => {
    const { page } = makePage();
    page.activity.add({ name: "call:17", timestamp: "2026-09-23 10:15:00", component: CallRow });

    expect(page.activity.has("comment:c2")).toBe(true);
    expect(page.activity.has("call:17")).toBe(true);
    expect(page.activity.has("comment:nope")).toBe(false);
  });

  it("gives the tab body only a script's rows to draw", () => {
    const { controller, page } = makePage();
    page.activity.add({ name: "call:17", timestamp: "2026-09-23 10:15:00", component: CallRow });

    expect(controller.activity.resolve().map((entry) => entry.item.name)).toEqual(["call:17"]);
  });
});

describe("what a script adds and removes", () => {
  it("drops a row with no component or no timestamp, and says why", () => {
    const { page } = makePage();

    page.activity.add({ name: "bare", timestamp: "2026-09-23 10:15:00" } as any);
    page.activity.add({ name: "timeless", component: CallRow } as any);

    expect(page.activity.has("bare")).toBe(false);
    expect(page.activity.has("timeless")).toBe(false);
    expect(warnings[0]).toContain("a row needs a component");
    expect(warnings[1]).toContain("a row needs a timestamp");
  });

  it("writes an ISO timestamp as the server writes one, so it sorts among the server's rows", () => {
    const { page } = makePage();

    page.activity.add({ name: "call:17", timestamp: "2026-09-23T10:15:00", component: CallRow });

    expect(page.activity.items[2]).toMatchObject({ name: "call:17", timestamp: "2026-09-23 10:15:00" });
    expect(warnings).toEqual([]);
  });

  it("drops a zone from a script's timestamp and warns, since server times are site-local", () => {
    const { page } = makePage();

    page.activity.add({ name: "a:1", timestamp: "2026-09-23T10:15:00.5Z", component: CallRow });
    page.activity.add({ name: "a:2", timestamp: "2026-09-23 10:16:00+05:30", component: CallRow });

    expect(page.activity.items.filter((item) => item.name.startsWith("a:")).map((item) => item.timestamp)).toEqual([
      "2026-09-23 10:15:00.5",
      "2026-09-23 10:16:00",
    ]);
    expect(warnings).toEqual([
      `[record-page] page.activity.add("a:1") — server times are site-local, so the zone "Z" was dropped.`,
      `[record-page] page.activity.add("a:2") — server times are site-local, so the zone "+05:30" was dropped.`,
    ]);
  });

  it("refuses a row under a server row's key", () => {
    const { controller, page } = makePage();

    page.activity.add({ name: "comment:c1", timestamp: "2026-09-23 12:00:00", component: CallRow });

    expect(controller.activity.resolve()).toEqual([]);
    expect(warnings[0]).toContain(`page.activity.add("comment:c1") — that name is a server row's`);
  });

  it("removes a script's own row, and leaves a server row where it is", () => {
    const { page } = makePage();
    page.activity.add({ name: "call:17", timestamp: "2026-09-23 10:15:00", component: CallRow });

    page.activity.remove("call:17");
    page.activity.remove("comment:c1");

    expect(page.activity.has("call:17")).toBe(false);
    expect(names(page.activity.items)).toEqual(["comment:c1", "version:v1-0", "comment:c2"]);
    expect(warnings[0]).toContain("a server row stays");
  });

  it("has no position words: time orders the list", () => {
    const { page } = makePage();

    (page.activity as any).move("comment:c2", { before: "comment:c1" });

    expect(names(page.activity.items)[0]).toBe("comment:c1");
    expect(warnings[0]).toContain("time orders this list");
  });

  it("keeps a script's row through a reload of the server's rows", async () => {
    const { page, reloads } = makePage();
    page.activity.add({ name: "call:17", timestamp: "2026-09-23 10:15:00", component: CallRow });

    await page.activity.reload();

    expect(reloads).toEqual(["activity"]);
    expect(page.activity.has("call:17")).toBe(true);
  });
});

describe("scrolling to a row", () => {
  it("hands the key to the host at once outside a replay", () => {
    const { page, scrolled } = makePage();

    page.activity.scrollTo("comment:c1");

    expect(scrolled).toEqual(["comment:c1"]);
  });

  it("warns naming the key when the list ended without it", async () => {
    const { page } = makePage({ scrollToActivity: async () => false });

    page.activity.scrollTo("comment:gone");
    await Promise.resolve();
    await Promise.resolve();

    expect(warnings[0]).toContain(`page.activity.scrollTo("comment:gone") — the list ended without it`);
  });

  it("waits for the replay to commit, and keeps only the last key", async () => {
    // The guide's act: read the last comment, scroll to it, add a row of its own.
    const drawnAtScroll: string[][] = [];
    registerRecordPage("CRM Deal", {
      onRefresh: (page) => {
        const last = page.activity.items.filter((row: any) => row.type === "comment").at(-1);
        page.activity.scrollTo("comment:c1");
        if (last) page.activity.scrollTo(last.name);
        page.activity.add({
          name: "call:17",
          timestamp: "2026-09-23 10:15:00",
          component: CallRow,
          props: { id: 17 },
        });
      },
    });
    const { controller, scrolled } = makePage({
      scrollToActivity: async (key) => {
        scrolled.push(key);
        drawnAtScroll.push(controller.activity.resolve().map((entry) => entry.item.name));
        return true;
      },
    });

    const replay = controller.refresh();
    expect(scrolled).toEqual([]);
    await replay;

    expect(scrolled).toEqual(["comment:c2"]);
    expect(drawnAtScroll).toEqual([["call:17"]]);
  });

  it("reports a host that throws, and the replay still settles", async () => {
    const errors = vi.spyOn(console, "error").mockImplementation(() => {});
    registerRecordPage("CRM Deal", { onRefresh: (page) => page.activity.scrollTo("comment:c1") });
    const { controller } = makePage({
      scrollToActivity: async () => {
        throw new Error("no feed");
      },
    });

    await controller.refresh();
    await Promise.resolve();

    expect(controller.ready.value).toBe(true);
    expect(errors.mock.calls[0][0]).toContain(`page.activity.scrollTo("comment:c1") — the host threw`);
  });
});

describe("the types the Activity tab shows", () => {
  it("shows every type until a script says otherwise", () => {
    const { controller } = makePage();

    expect(controller.activity.shownTypes()).toBeNull();
  });

  it("stages a replay's list and commits it with the replay", async () => {
    const seen: unknown[] = [];
    registerRecordPage("CRM Deal", {
      onRefresh: (page) => {
        page.activity.types(["comment", "email"]);
        seen.push(controller.activity.shownTypes());
      },
    });
    const { controller } = makePage();

    await controller.refresh();

    expect(seen).toEqual([null]);
    expect(controller.activity.shownTypes()).toEqual(["comment", "email"]);
  });

  it("goes back to every type when a replay no longer sets it", async () => {
    let narrow = true;
    registerRecordPage("CRM Deal", {
      onRefresh: (page) => {
        if (narrow) page.activity.types(["comment"]);
      },
    });
    const { controller } = makePage();
    await controller.refresh();

    narrow = false;
    await controller.refresh();

    expect(controller.activity.shownTypes()).toBeNull();
  });

  it("does not wake the host when a replay sets the same list again", async () => {
    registerRecordPage("CRM Deal", {
      onRefresh: (page) => page.activity.types(["comment", { version: ["status"] }]),
    });
    const { controller } = makePage();
    await controller.refresh();
    const changes = vi.fn();
    watch(() => controller.activity.shownTypes(), changes, { flush: "sync" });

    await controller.refresh();

    expect(changes).not.toHaveBeenCalled();
  });

  it("applies at once outside a replay", () => {
    const { controller, page } = makePage();

    page.activity.types(["email"]);

    expect(controller.activity.shownTypes()).toEqual(["email"]);
  });
});
