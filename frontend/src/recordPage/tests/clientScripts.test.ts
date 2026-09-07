// The Client Script tier as executable claims.
import { beforeEach, describe, expect, it, vi } from "vitest";

const { call, toast, evaluateClientScript } = vi.hoisted(() => ({
  call: vi.fn(),
  toast: { success: vi.fn(), error: vi.fn() },
  // Blob-URL modules are the real mechanism, but node cannot import one; the
  // evaluator's own contract is the browser verification's job.
  evaluateClientScript: vi.fn(),
}));

vi.mock("frappe-ui", () => ({ call, toast }));
vi.mock("../evaluateClientScript", () => ({ evaluateClientScript }));

import {
  canWriteClientScripts,
  loadClientScripts,
  reloadClientScripts,
  resetClientScripts,
} from "../clientScripts";
import { registrationsFor, resetRegistry } from "../registry";

function respond(scripts: string[], canWrite = true) {
  call.mockResolvedValue({
    scripts: scripts.map((name) => ({ name, script: "export default {}" })),
    can_write: canWrite,
  });
}

function sources(doctype = "CRM Deal") {
  return registrationsFor(doctype).map((registration) => registration.source);
}

describe("the Client Script tier", () => {
  beforeEach(() => {
    resetRegistry();
    resetClientScripts();
    call.mockReset();
    toast.error.mockReset();
    evaluateClientScript.mockReset();
    evaluateClientScript.mockImplementation(async () => ({ onRefresh: () => {} }));
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  it("registers the doctype's scripts as sources, in the order served", async () => {
    respond(["oldest", "newest"]);
    await loadClientScripts("CRM Deal");
    expect(sources()).toEqual(["client-script:oldest", "client-script:newest"]);
  });

  it("fetches once per doctype", async () => {
    respond(["only"]);
    await loadClientScripts("CRM Deal");
    await loadClientScripts("CRM Deal");
    expect(call).toHaveBeenCalledTimes(1);
  });

  it("skips a script that fails to load, keeping the rest of the tier", async () => {
    respond(["broken", "fine"]);
    evaluateClientScript.mockImplementation(async (row: { name: string }) => {
      if (row.name === "broken") throw new SyntaxError("Unexpected token");
      return { onRefresh: () => {} };
    });
    await loadClientScripts("CRM Deal");
    expect(sources()).toEqual(["client-script:fine"]);
  });

  it("toasts a failure once per script, only for script editors", async () => {
    respond(["broken"], false);
    evaluateClientScript.mockRejectedValue(new SyntaxError("Unexpected token"));
    await loadClientScripts("CRM Deal");
    expect(toast.error).not.toHaveBeenCalled();

    respond(["broken"], true);
    await reloadClientScripts("CRM Deal");
    await reloadClientScripts("CRM Deal");
    expect(toast.error).toHaveBeenCalledTimes(1);
  });

  it("re-registers the whole tier on reload, so creation order survives a save", async () => {
    respond(["oldest", "newest"]);
    await loadClientScripts("CRM Deal");
    await reloadClientScripts("CRM Deal");
    expect(sources()).toEqual(["client-script:oldest", "client-script:newest"]);
  });

  it("drops a deleted script's source on reload", async () => {
    respond(["kept", "deleted"]);
    await loadClientScripts("CRM Deal");
    respond(["kept"]);
    await reloadClientScripts("CRM Deal");
    expect(sources()).toEqual(["client-script:kept"]);
  });

  it("lets the later of two overlapping reloads win, with no doubled source", async () => {
    respond(["stale"]);
    await loadClientScripts("CRM Deal");

    let releaseStale = (_: unknown) => {};
    call.mockReturnValueOnce(
      new Promise((resolve) => (releaseStale = resolve)),
    );
    const slow = reloadClientScripts("CRM Deal");

    respond(["fresh"]);
    await reloadClientScripts("CRM Deal");
    releaseStale({
      scripts: [{ name: "stale", script: "export default {}" }],
      can_write: true,
    });
    await slow;

    expect(sources()).toEqual(["client-script:fresh"]);
  });

  // The editor's entry affordance is gated on this, and the tier's fetch is the
  // only thing that asks the server the question.
  it("publishes whether the session may write Client Scripts", async () => {
    expect(canWriteClientScripts.value).toBe(false);

    respond(["one"], true);
    await loadClientScripts("CRM Deal");
    expect(canWriteClientScripts.value).toBe(true);

    respond(["one"], false);
    await reloadClientScripts("CRM Deal");
    expect(canWriteClientScripts.value).toBe(false);
  });

  it("leaves the client scriptless when the fetch fails", async () => {
    call.mockRejectedValue(new Error("offline"));
    await loadClientScripts("CRM Deal");
    expect(sources()).toEqual([]);
  });
});
