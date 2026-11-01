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
    addFileScript("CRM Deal", { app: "crm", load: async () => ({ default: { onRefresh: () => {} } }) });
    addFileScript("CRM Deal", { app: "erpnext", load: async () => ({ default: { onRefresh: () => {} } }) });
    respond(["stored"]);

    await loadRecordScripts("CRM Deal");

    expect(sources("CRM Deal")).toEqual(["crm", "erpnext", "client-script:stored"]);
  });

  it("registers the file scripts once, however often the doctype loads again", async () => {
    addFileScript("CRM Lead", { app: "crm", load: async () => ({ default: { onRefresh: () => {} } }) });
    respond(["stored"]);
    await loadRecordScripts("CRM Lead");

    invalidateClientScripts("CRM Lead");
    await loadRecordScripts("CRM Lead");
    await loadRecordScripts("CRM Lead");

    expect(sources("CRM Lead")).toEqual(["crm", "client-script:stored"]);
  });

  it("leaves another doctype's file scripts for that doctype's first load", async () => {
    addFileScript("CRM Note", { app: "crm", load: async () => ({ default: { onRefresh: () => {} } }) });
    addFileScript("CRM Task", { app: "crm", load: async () => ({ default: { onRefresh: () => {} } }) });
    respond([]);

    await loadRecordScripts("CRM Note");

    expect(sources("CRM Task")).toEqual([]);
    await loadRecordScripts("CRM Task");
    expect(sources("CRM Task")).toEqual(["crm"]);
  });

  it("fetches no file script until its doctype loads", async () => {
    const load = vi.fn(async () => ({ default: { onRefresh: () => {} } }));
    addFileScript("CRM Call Log", { app: "crm", load });
    respond([]);

    await loadRecordScripts("CRM Note");
    expect(load).not.toHaveBeenCalled();

    await loadRecordScripts("CRM Call Log");
    expect(load).toHaveBeenCalledTimes(1);
  });

  it("fetches once when the page asks twice before the first fetch ends", async () => {
    const load = vi.fn(async () => ({ default: { onRefresh: () => {} } }));
    addFileScript("CRM Org", { app: "crm", load });
    respond([]);

    await Promise.all([loadRecordScripts("CRM Org"), loadRecordScripts("CRM Org")]);

    expect(load).toHaveBeenCalledTimes(1);
    expect(sources("CRM Org")).toEqual(["crm"]);
  });

  it("registers in the order added however the fetches finish", async () => {
    const slow = new Promise<{ default: object }>((resolve) =>
      setTimeout(() => resolve({ default: { onRefresh: () => {} } }), 10),
    );
    addFileScript("CRM Slow", { app: "crm", load: () => slow });
    addFileScript("CRM Slow", { app: "erpnext", load: async () => ({ default: { onRefresh: () => {} } }) });
    respond([]);

    await loadRecordScripts("CRM Slow");

    expect(sources("CRM Slow")).toEqual(["crm", "erpnext"]);
  });

  it("tries a failed fetch again on the next load, and still loads the Client Scripts", async () => {
    const error = vi.spyOn(console, "error").mockImplementation(() => {});
    const load = vi
      .fn()
      .mockRejectedValueOnce(new Error("chunk failed"))
      .mockResolvedValue({ default: { onRefresh: () => {} } });
    addFileScript("CRM Retry", { app: "crm", load });
    respond(["stored"]);

    await loadRecordScripts("CRM Retry");
    expect(sources("CRM Retry")).toEqual(["client-script:stored"]);
    expect(error).toHaveBeenCalled();

    invalidateClientScripts("CRM Retry");
    await loadRecordScripts("CRM Retry");
    expect(sources("CRM Retry")).toEqual(["crm", "client-script:stored"]);
  });

  it("asks for the Client Scripts while the file scripts are still downloading", async () => {
    let arrive!: () => void;
    const slow = new Promise<{ default: object }>((resolve) => {
      arrive = () => resolve({ default: { onRefresh: () => {} } });
    });
    addFileScript("CRM Beside", { app: "crm", load: () => slow });
    respond(["stored"]);

    const loading = loadRecordScripts("CRM Beside");
    await vi.waitFor(() => expect(call).toHaveBeenCalled());
    expect(sources("CRM Beside")).toEqual([]);

    arrive();
    await loading;
    expect(sources("CRM Beside")).toEqual(["crm", "client-script:stored"]);
  });

  it("skips a script with no default export and warns", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    addFileScript("CRM Bare", { app: "crm", load: async () => ({}) });
    respond([]);

    await loadRecordScripts("CRM Bare");

    expect(sources("CRM Bare")).toEqual([]);
    expect(warn).toHaveBeenCalledWith(expect.stringContaining("crm's record script for CRM Bare"));
  });
});
