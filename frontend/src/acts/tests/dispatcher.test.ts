// The dispatcher on its own: a scope's surfaces by name, and a later scope taking a name over.
import { describe, expect, it, vi } from "vitest";

vi.mock("frappe-ui", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("@framework/ui/api", () => ({ getTranslations: vi.fn() }));

import { ActDenied, ActDispatcher, type ActScope } from "../dispatcher";

describe("the dispatcher", () => {
  it("keeps a newer scope's surface when an older scope lets go", async () => {
    const dispatcher = new ActDispatcher();
    const older = scope("older");
    const newer = scope("newer");
    const releaseOlder = dispatcher.register(older);
    dispatcher.register(newer);

    releaseOlder();
    await dispatcher.run("header.go");

    expect(newer.ran).toEqual(["newer"]);
    expect(older.ran).toEqual([]);
  });

  it("splits a full name at its first dot, so an item name may hold more", async () => {
    const dispatcher = new ActDispatcher();
    const ran: string[] = [];
    dispatcher.register({
      ...scope("shell"),
      surfaces: { shell: () => [{ item: { name: "crm.log_a_call", run: () => void ran.push("call") }, hidden: false }] },
    });

    await dispatcher.run("shell.crm.log_a_call");

    expect(ran).toEqual(["call"]);
    expect(dispatcher.available().map((act) => act.name)).toEqual(["shell.crm.log_a_call"]);
  });

  it("waits for a right to settle before it checks it", async () => {
    const dispatcher = new ActDispatcher();
    let loaded = false;
    let settles = 1;
    const ran: string[] = [];
    dispatcher.register({
      ...scope("page"),
      surfaces: {
        header: () => [{ item: { name: "convert", right: { doctype: "CRM Deal", ptype: "create" }, run: () => void ran.push("convert") }, hidden: false }],
      },
      passes: () => loaded,
      settled: async () => {
        if (settles-- > 0) loaded = true;
      },
    });

    await dispatcher.run("header.convert");
    loaded = false;
    const denied = await dispatcher.run("header.convert").catch((error) => error);

    expect(ran).toEqual(["convert"]);
    expect(denied).toBeInstanceOf(ActDenied);
  });
});

function scope(label: string): ActScope & { ran: string[] } {
  const ran: string[] = [];
  return {
    ran,
    surfaces: { header: () => [{ item: { name: "go", run: () => void ran.push(label) }, hidden: false }] },
    context: () => null,
    passes: () => true,
    settled: async () => {},
    hold: async (work) => work(),
    failed: () => {},
  };
}
