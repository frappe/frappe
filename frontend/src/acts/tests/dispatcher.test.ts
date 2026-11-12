// The dispatcher on its own: a scope's surfaces by name, and a later scope taking a name over.
import { describe, expect, it, vi } from "vitest";
import { ref } from "vue";

vi.mock("frappe-ui", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("@framework/ui/api", () => ({ getTranslations: vi.fn() }));

import { ActDenied, ActDispatcher, passesRight, passesWhen, type ActScope } from "../dispatcher";

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

  it("drops the surface once both scopes have let go, whichever order they release in", async () => {
    const dispatcher = new ActDispatcher();
    const releaseOlder = dispatcher.register(scope("older"));
    const releaseNewer = dispatcher.register(scope("newer"));

    releaseOlder();
    releaseNewer();

    expect(dispatcher.available()).toEqual([]);
    await expect(dispatcher.run("header.go")).rejects.toBeInstanceOf(ActDenied);
  });

  it("gives a surface back to the scope a newer one shadowed when the newer lets go", async () => {
    const dispatcher = new ActDispatcher();
    const older = scope("older");
    const newer = scope("newer");
    dispatcher.register(older);
    const releaseNewer = dispatcher.register(newer);

    await dispatcher.run("header.go");
    releaseNewer();
    await dispatcher.run("header.go");

    expect(newer.ran).toEqual(["newer"]);
    expect(older.ran).toEqual(["older"]);
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

  it("runs nothing when another scope took the surface while the right settled", async () => {
    const dispatcher = new ActDispatcher();
    let release = () => {};
    const ran: string[] = [];
    const entry = (label: string) => () => [
      { item: { name: "convert", right: "write", run: () => void ran.push(label) }, hidden: false },
    ];
    dispatcher.register({
      ...scope("old"),
      surfaces: { header: entry("old") },
      settled: () => new Promise<void>((resolve) => (release = resolve)),
    });

    const asked = dispatcher.run("header.convert").catch((error) => error);
    dispatcher.register({ ...scope("new"), surfaces: { header: entry("new") } });
    release();

    expect(await asked).toMatchObject({ reason: "missing" });
    expect(ran).toEqual([]);
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
      settled: () =>
        settles-- > 0 ? Promise.resolve().then(() => void (loaded = true)) : undefined,
    });

    await dispatcher.run("header.convert");
    loaded = false;
    const denied = await dispatcher.run("header.convert").catch((error) => error);

    expect(ran).toEqual(["convert"]);
    expect(denied).toBeInstanceOf(ActDenied);
  });
});

describe("an act's when", () => {
  function whenScope(when?: (context: any) => boolean) {
    const ran: string[] = [];
    const dispatcher = new ActDispatcher();
    dispatcher.register({
      ...scope("page"),
      context: () => ({ medium: "twilio" }),
      surfaces: { header: () => [{ item: { name: "call", when, run: () => void ran.push("call") }, hidden: false }] },
    });
    return { dispatcher, ran };
  }

  it("lists and runs an act with no when, or a when that holds for the scope's context", async () => {
    const seen: unknown[] = [];
    const { dispatcher, ran } = whenScope((context) => (seen.push(context), true));

    await dispatcher.run("header.call");

    expect(dispatcher.available().map((act) => act.name)).toEqual(["header.call"]);
    expect(dispatcher.find("header.call")).toBeDefined();
    expect(ran).toEqual(["call"]);
    expect(seen[0]).toEqual({ medium: "twilio" });
    expect(whenScope().dispatcher.available()).toHaveLength(1);
  });

  it("keeps an act whose when is false out of every read and rejects it as hidden", async () => {
    const { dispatcher, ran } = whenScope(() => false);

    expect(dispatcher.available()).toEqual([]);
    expect(dispatcher.find("header.call")).toBeUndefined();
    await expect(dispatcher.run("header.call")).rejects.toMatchObject({ reason: "hidden" });
    expect(ran).toEqual([]);
  });

  it("follows the state its when reads", async () => {
    const medium = ref<string | null>(null);
    const { dispatcher, ran } = whenScope(() => !!medium.value);

    expect(dispatcher.available()).toEqual([]);
    medium.value = "twilio";
    await dispatcher.run("header.call");

    expect(dispatcher.available().map((act) => act.name)).toEqual(["header.call"]);
    expect(ran).toEqual(["call"]);
  });

  it("hides an act whose when throws, and says so", () => {
    const error = vi.spyOn(console, "error").mockImplementation(() => {});
    const { dispatcher } = whenScope(() => {
      throw new Error("no state yet");
    });

    expect(dispatcher.available()).toEqual([]);
    expect(error).toHaveBeenCalled();
    error.mockRestore();
  });
});

describe("passesWhen", () => {
  it("passes an item with no when, and asks a when with the scope's context", () => {
    const scope = { context: () => "ctx" };
    expect(passesWhen(scope, {})).toBe(true);
    expect(passesWhen(scope, { when: (context) => context === "ctx" })).toBe(true);
    expect(passesWhen(scope, { when: () => false })).toBe(false);
  });
});

describe("passesRight", () => {
  it("fails a right that has not settled, even while passes says yes", () => {
    const loading = { passes: () => true, settled: () => new Promise<void>(() => {}) };
    const loaded = { passes: () => true, settled: () => undefined };
    expect(passesRight(loading, { right: "delete" })).toBe(false);
    expect(passesRight(loaded, { right: "delete" })).toBe(true);
    expect(passesRight(loading, {})).toBe(true);
  });
});

function scope(label: string): ActScope & { ran: string[] } {
  const ran: string[] = [];
  return {
    ran,
    surfaces: { header: () => [{ item: { name: "go", run: () => void ran.push(label) }, hidden: false }] },
    context: () => null,
    passes: () => true,
    settled: () => undefined,
    hold: async (work) => work(),
    failed: () => {},
  };
}
