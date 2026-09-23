// `page.files` as executable claims: the record's attachments under their File
// names, oldest first, with a script's own rows placed among them by time.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
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
vi.mock("@framework/ui/api", () => ({
  runMethod: vi.fn(async () => ({ data: null })),
  getMeta: vi.fn(async () => ({ data: null })),
}));

import { createRecordPage, type RecordPageHost } from "../createRecordPage";
import { registerRecordPage, resetRegistry } from "../registry";
import type { FileRow } from "../types";

const LinkRow = { render: () => null };

const FILES: FileRow[] = [
  {
    name: "f-quote",
    file_name: "quote.pdf",
    file_url: "/private/files/quote.pdf",
    is_private: 1,
    creation: "2026-09-20 09:00:00",
    owner: "a@example.com",
  },
  {
    name: "f-logo",
    file_name: "logo.png",
    file_url: "/files/logo.png",
    is_private: 0,
    creation: "2026-09-22 09:00:00",
    owner: "b@example.com",
  },
];

function makePage() {
  const reloads: string[] = [];
  const host: RecordPageHost = {
    doctype: "CRM Deal",
    docname: "CRM-DEAL-1",
    doc: ref({}),
    saved: ref({}),
    meta: ref(null),
    perms: () => ({}),
    isDirty: () => false,
    activeTab: () => "files",
    activateTab: () => {},
    save: async () => {},
    reload: async () => {},
    router: {} as any,
    activityRows: () => [],
    scrollToActivity: async () => true,
    reloadActivity: async () => {},
    fileRows: () => FILES,
    reloadFiles: async () => void reloads.push("files"),
  };
  const controller = createRecordPage(host);
  return { controller, page: controller.page, reloads };
}

const names = (items: readonly { name: string }[]) => items.map((item) => item.name);

let warnings: string[];

beforeEach(() => {
  resetRegistry();
  warnings = [];
  vi.spyOn(console, "warn").mockImplementation((message: string) => void warnings.push(message));
});

afterEach(() => vi.restoreAllMocks());

describe("page.files", () => {
  it("hands each attachment back under its File name, oldest first", () => {
    const { page } = makePage();

    expect(page.files.items[0]).toEqual(FILES[0]);
    expect(names(page.files.items)).toEqual(["f-quote", "f-logo"]);
  });

  it("places a script's row by its timestamp among the attachments", async () => {
    registerRecordPage("CRM Deal", {
      onRefresh: (page) =>
        page.files.add({ name: "drive-link", timestamp: "2026-09-21 12:00:00", component: LinkRow }),
    });
    const { controller, page } = makePage();

    await controller.refresh();

    expect(names(page.files.items)).toEqual(["f-quote", "drive-link", "f-logo"]);
    expect(controller.files.resolve().map((entry) => entry.item.name)).toEqual(["drive-link"]);
  });

  it("writes an ISO timestamp as the server writes one before placing the row", () => {
    const { page } = makePage();

    page.files.add({ name: "drive-link", timestamp: "2026-09-21T12:00:00", component: LinkRow });

    expect(names(page.files.items)).toEqual(["f-quote", "drive-link", "f-logo"]);
    expect(page.files.items[1].timestamp).toBe("2026-09-21 12:00:00");
  });

  it("removes a script's own row, and leaves an attachment where it is", () => {
    const { page } = makePage();
    page.files.add({ name: "drive-link", timestamp: "2026-09-21 12:00:00", component: LinkRow });

    page.files.remove("drive-link");
    page.files.remove("f-logo");

    expect(page.files.has("drive-link")).toBe(false);
    expect(page.files.has("f-logo")).toBe(true);
    expect(warnings[0]).toContain(`page.files.remove("f-logo") — a server row stays`);
  });

  it("keeps a script's row through a reload of the attachments", async () => {
    const { page, reloads } = makePage();
    page.files.add({ name: "drive-link", timestamp: "2026-09-21 12:00:00", component: LinkRow });

    await page.files.reload();

    expect(reloads).toEqual(["files"]);
    expect(page.files.has("drive-link")).toBe(true);
  });

  it("refuses a write to the list", () => {
    const { page } = makePage();
    vi.spyOn(console, "error").mockImplementation(() => {});

    expect(() => ((page.files.items[0] as any).file_name = "x.pdf")).toThrow("page.files.items");
    expect(FILES[0].file_name).toBe("quote.pdf");
  });
});
