// The record page's one script loader: file scripts, then the Client Script tier.
import { beforeEach, describe, expect, it, vi } from "vitest";

const { call } = vi.hoisted(() => ({ call: vi.fn() }));

vi.mock("frappe-ui", () => ({ toast: { error: vi.fn() } }));
vi.mock("@framework/ui/api", () => ({ runMethod: call }));
vi.mock("../evaluateClientScript", () => ({
  evaluateClientScript: async () => ({ onRefresh: () => {} }),
}));

import { invalidateClientScripts, resetClientScripts } from "../clientScripts";
import { registrationsFor, resetRegistry } from "../registry";
import { addFileScript, loadRecordScripts } from "../scriptLoader";

function respond(scripts: string[]) {
  call.mockResolvedValue({
    data: {
      scripts: scripts.map((name) => ({ name, script: "export default {}" })),
      can_write: false,
    },
  });
}

function sources(doctype: string) {
  return registrationsFor(doctype).map((registration) => registration.source);
}

describe("the record page's script loader", () => {
  beforeEach(() => {
    resetRegistry();
    resetClientScripts();
    call.mockReset();
  });

  it("registers the doctype's file scripts in the order added, then its Client Scripts", async () => {
    addFileScript("CRM Deal", { app: "crm", handlers: { onRefresh: () => {} } });
    addFileScript("CRM Deal", { app: "erpnext", handlers: { onRefresh: () => {} } });
    respond(["stored"]);

    await loadRecordScripts("CRM Deal");

    expect(sources("CRM Deal")).toEqual(["crm", "erpnext", "client-script:stored"]);
  });

  it("registers the file scripts once, however often the doctype loads again", async () => {
    addFileScript("CRM Lead", { app: "crm", handlers: { onRefresh: () => {} } });
    respond(["stored"]);
    await loadRecordScripts("CRM Lead");

    invalidateClientScripts("CRM Lead");
    await loadRecordScripts("CRM Lead");
    await loadRecordScripts("CRM Lead");

    expect(sources("CRM Lead")).toEqual(["crm", "client-script:stored"]);
  });

  it("leaves another doctype's file scripts for that doctype's first load", async () => {
    addFileScript("CRM Note", { app: "crm", handlers: { onRefresh: () => {} } });
    addFileScript("CRM Task", { app: "crm", handlers: { onRefresh: () => {} } });
    respond([]);

    await loadRecordScripts("CRM Note");

    expect(sources("CRM Task")).toEqual([]);
    await loadRecordScripts("CRM Task");
    expect(sources("CRM Task")).toEqual(["crm"]);
  });
});
