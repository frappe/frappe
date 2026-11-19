// The Export dialog's hint under Module, and the file it writes once a module is chosen.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, nextTick, type App } from "vue";

const { listDocuments } = vi.hoisted(() => ({ listDocuments: vi.fn() }));
vi.mock("@framework/ui/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@framework/ui/api")>()),
  listDocuments,
}));

import ExportCustomizationsDialog from "../ExportCustomizationsDialog.vue";

let app: App | undefined;
afterEach(() => {
  app?.unmount();
  app = undefined;
  document.body.innerHTML = "";
});

const NONE = { custom_fields: 0, property_setters: 0, layouts: 0 };

async function mount(module: string, doctype = "Sales Invoice", changes = NONE) {
  listDocuments.mockResolvedValue({
    data: [
      { name: "Accounts", app_name: "erpnext" },
      { name: "Desk", app_name: "frappe" },
      { name: "Point-of-Sale & Co", app_name: "erpnext" },
    ],
  });
  const host = document.body.appendChild(document.createElement("div"));
  app = createApp(ExportCustomizationsDialog, {
    doctype,
    module,
    changes,
    close: vi.fn(),
  });
  app.mount(host);
  await vi.waitFor(() => expect(listDocuments).toHaveBeenCalled());
  await nextTick();
  return host;
}

describe("the Export dialog", () => {
  it("names what this site changed, or that it changed nothing", async () => {
    let host = await mount("Accounts");
    expect(host.querySelector("[data-export-changes]")!.textContent!.trim()).toBe("No site changes yet");
    app!.unmount();
    host = await mount("Accounts", "Sales Invoice", { custom_fields: 2, property_setters: 1, layouts: 0 });
    expect(host.querySelector("[data-export-changes]")!.textContent!.trim()).toBe("2 custom fields, 1 property change");
  });

  it("writes the file in the module's app, with no Cancel button", async () => {
    const host = await mount("Accounts");
    expect(host.querySelector("[data-export-file]")!.textContent).toContain(
      "erpnext/accounts/custom/sales_invoice.json",
    );
    expect(
      [...host.querySelectorAll("button")].map((button) =>
        button.textContent!.trim(),
      ),
    ).not.toContain("Cancel");
  });

  it("scrubs the path as the server does: spaces and hyphens only", async () => {
    const host = await mount("Point-of-Sale & Co", "Sales-Order Item & Tax");
    expect(host.querySelector("[data-export-file]")!.textContent).toContain(
      "erpnext/point_of_sale_&_co/custom/sales_order_item_&_tax.json",
    );
  });

  it("names what the hint holds while the module has no app", async () => {
    const host = await mount("Nowhere");
    expect(host.querySelector("[data-export-file]")!.textContent).toContain(
      "The app and the folder the file goes in.",
    );
  });

  it("hands focus back to the More button when it closes", async () => {
    const more = document.body.appendChild(document.createElement("button"));
    more.setAttribute("data-editor-more", "");
    await mount("Accounts");
    expect(document.activeElement).not.toBe(more);
    app!.unmount();
    app = undefined;
    expect(document.activeElement).toBe(more);
  });
});
