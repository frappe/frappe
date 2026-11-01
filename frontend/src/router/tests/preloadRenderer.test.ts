// The router starts loading a view type's renderer when an address names the type, after the frame paints.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { registerStandardPages, viewRenderers } from "@/contributions/registry";
import { standardPages } from "@/pages/standardPages";
import { createShellRouter } from "@/router";

registerStandardPages(standardPages);

vi.mock("@/pages/List.vue", () => ({ default: { render: () => null } }));
vi.mock("@/pages/Record.vue", () => ({ default: { render: () => null } }));
vi.mock("@/shell/NotFound.vue", () => ({ default: { render: () => null } }));

const addresses = new Addresses({
  doctypes: { "Sales Invoice": ["sales-invoice", "accounts"] },
  modules: { accounts: "Accounts" },
  singles: [],
});

const boot = {
  app: "erpnext",
  shell_base: "/apps/erpnext",
  prefixes: { erpnext: { app: "erpnext", modular: false } },
  view_types: [
    { name: "List", label: "List" },
    { name: "Kanban", label: "Kanban" },
  ],
} as unknown as Boot;

const list = vi.fn(async () => ({}));
const kanban = vi.fn(async () => ({}));

beforeEach(() => {
  list.mockClear();
  kanban.mockClear();
  viewRenderers.List = list;
  viewRenderers.Kanban = kanban;
  // Nothing has painted, so the frame has nothing to wait for.
  vi.spyOn(performance, "getEntriesByName").mockReturnValue([]);
});

afterEach(() => {
  delete viewRenderers.List;
  delete viewRenderers.Kanban;
  vi.restoreAllMocks();
});

async function open(path: string) {
  const router = createShellRouter(boot, addresses);
  await router.push(path);
  await new Promise((resolve) => setTimeout(resolve));
}

describe("preloading a view type's renderer", () => {
  it("loads the renderer of the type the address names, and no other", async () => {
    await open("/sales-invoice/view/kanban");

    expect(kanban).toHaveBeenCalledOnce();
    expect(list).not.toHaveBeenCalled();
  });

  it("loads the List renderer for the main address and for /view/list", async () => {
    await open("/sales-invoice");
    await open("/sales-invoice/view/list");

    expect(list).toHaveBeenCalledTimes(2);
    expect(kanban).not.toHaveBeenCalled();
  });

  it("loads nothing for a saved view's own key, which names no type", async () => {
    await open("/sales-invoice/view/open-invoices");

    expect(list).not.toHaveBeenCalled();
    expect(kanban).not.toHaveBeenCalled();
  });

  it("loads nothing for a type with no renderer, and a failed load does not fail the navigation", async () => {
    delete viewRenderers.Kanban;
    await open("/sales-invoice/view/kanban");
    expect(kanban).not.toHaveBeenCalled();

    kanban.mockRejectedValueOnce(new Error("offline"));
    viewRenderers.Kanban = kanban;
    await expect(open("/sales-invoice/view/kanban")).resolves.toBeUndefined();
  });
});
