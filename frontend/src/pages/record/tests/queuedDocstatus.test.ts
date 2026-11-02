// A queued Submit or Cancel: the call resolves `{ queued: true }`, a failed job toasts once, a finished one fires `after*` once.
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/i18n", () => ({
  __: (text: string, values: string[] = []) =>
    text.replace("{0}", values[0] ?? ""),
}));

const server = vi.hoisted(() => ({
  answer: {} as Record<string, any>,
  failure: undefined as Error | undefined,
}));
vi.mock("@framework/ui/api", () => ({
  runMethod: async () => ({ data: { queued: true } }),
  getDocument: async () => ({ data: server.answer }),
  runDocumentMethod: async () => {
    if (server.failure) throw server.failure;
    return { data: server.answer };
  },
}));

import {
  DocstatusMover,
  queueFailureMessage,
  type DocstatusHost,
} from "../queuedDocstatus";

function socket() {
  const handlers = new Map<string, Set<(...args: unknown[]) => void>>();
  const of = (event: string) =>
    handlers.get(event) ?? handlers.set(event, new Set()).get(event)!;
  return {
    emit: vi.fn(),
    on: (event: string, handler: (...args: unknown[]) => void) =>
      void of(event).add(handler),
    off: (event: string, handler: (...args: unknown[]) => void) =>
      void of(event).delete(handler),
    send: async (event: string, payload: unknown) => {
      await Promise.all([...of(event)].map((handler) => handler(payload)));
    },
    count: () => of("doc_update").size + of("submission_failed").size,
  };
}

function makeMover(overrides: Partial<DocstatusHost> = {}) {
  const live = socket();
  const record = { docstatus: 0 };
  const mocks = {
    socket: live,
    queueing: () => true,
    isDirty: () => false,
    load: vi.fn(async () => record),
    take: vi.fn(async () => {}),
    fire: vi.fn(async () => {}),
    info: vi.fn(),
    failed: vi.fn(),
    error: vi.fn(),
  };
  const mover = new DocstatusMover({ ...mocks, ...overrides } as DocstatusHost);
  return { live, record, host: mocks, mover };
}

// A reload that stays open until `finish()`.
function slowLoad() {
  const record = { docstatus: 0 };
  const open: (() => void)[] = [];
  const load = vi.fn(async () => {
    await new Promise<void>((resolve) => open.push(resolve));
    return record;
  });
  return { load, record, finish: () => open.forEach((resolve) => resolve()) };
}

const FAILURE = {
  name: "SQ-1",
  ref_doctype: "Invoice",
  ref_docname: "INV-1",
  exception: "Insufficient stock",
};

beforeEach(() => {
  server.failure = undefined;
  server.answer = { name: "INV-1", docstatus: 0 };
});

describe("moving a record through the Submission Queue", () => {
  it("resolves { queued: true } and says so when the record did not move", async () => {
    const { host, mover } = makeMover();

    await expect(mover.move("submit", "Invoice", "INV-1")).resolves.toEqual({
      queued: true,
    });

    expect(host.info).toHaveBeenCalledWith(
      expect.stringContaining("Queued for Submit"),
    );
    expect(host.take).not.toHaveBeenCalled();
  });

  it("hands Cancel all to the background without watching a Submission Queue row", async () => {
    server.answer = {};
    const { host, live, mover } = makeMover();

    await expect(
      mover.move("cancel", "Invoice", "INV-1", { all: true, docs: null }),
    ).resolves.toEqual({
      queued: true,
    });

    expect(host.info).toHaveBeenCalledWith(
      expect.stringContaining("cancelled in the background"),
    );
    expect(live.count()).toBe(0);
  });

  it("takes the record and resolves nothing when the act ran at once", async () => {
    server.answer = { name: "INV-1", docstatus: 1 };
    const { host, live, mover } = makeMover({ queueing: () => false });

    await expect(
      mover.move("submit", "Invoice", "INV-1"),
    ).resolves.toBeUndefined();

    expect(host.take).toHaveBeenCalledWith(server.answer);
    expect(live.count()).toBe(0);
  });

  it("fires afterSubmit once, after the page holds the submitted record", async () => {
    const { host, live, mover, record } = makeMover();
    await mover.move("submit", "Invoice", "INV-1");

    await live.send("doc_update", { doctype: "Invoice", name: "INV-2" });
    expect(host.load).not.toHaveBeenCalled();
    record.docstatus = 1;
    await live.send("doc_update", { doctype: "Invoice", name: "INV-1" });
    await live.send("doc_update", { doctype: "Invoice", name: "INV-1" });

    expect(host.fire).toHaveBeenCalledTimes(1);
    expect(host.fire).toHaveBeenCalledWith("afterSubmit");
    expect(host.load.mock.invocationCallOrder[0]).toBeLessThan(
      host.fire.mock.invocationCallOrder[0],
    );
    expect(host.failed).not.toHaveBeenCalled();
    expect(live.count()).toBe(0);
  });

  it("fires afterCancel when a queued Cancel finishes", async () => {
    server.answer = { name: "INV-1", docstatus: 1 };
    const { host, live, mover, record } = makeMover();
    await mover.move("cancel", "Invoice", "INV-1");

    record.docstatus = 2;
    await live.send("doc_update", { doctype: "Invoice", name: "INV-1" });

    expect(host.fire).toHaveBeenCalledWith("afterCancel");
  });

  it("waits again when the record updated but did not move", async () => {
    const { host, live, mover, record } = makeMover();
    await mover.move("submit", "Invoice", "INV-1");

    await live.send("doc_update", { doctype: "Invoice", name: "INV-1" });
    expect(host.fire).not.toHaveBeenCalled();
    record.docstatus = 1;
    await live.send("doc_update", { doctype: "Invoice", name: "INV-1" });

    expect(host.fire).toHaveBeenCalledTimes(1);
  });

  it("fires once when two updates arrive during one reload", async () => {
    const { load, finish, record } = slowLoad();
    const { host, live, mover } = makeMover({ load });
    await mover.move("submit", "Invoice", "INV-1");
    record.docstatus = 1;

    const updates = Promise.all([
      live.send("doc_update", { doctype: "Invoice", name: "INV-1" }),
      live.send("doc_update", { doctype: "Invoice", name: "INV-1" }),
    ]);
    await vi.waitFor(() => expect(load).toHaveBeenCalledTimes(2));
    finish();
    await updates;

    expect(host.fire).toHaveBeenCalledTimes(1);
  });

  it("still reports a failure that arrives while a reload is running", async () => {
    const { load, finish, record } = slowLoad();
    const { host, live, mover } = makeMover({ load });
    await mover.move("submit", "Invoice", "INV-1");

    const update = live.send("doc_update", {
      doctype: "Invoice",
      name: "INV-1",
    });
    await vi.waitFor(() => expect(load).toHaveBeenCalled());
    await live.send("submission_failed", FAILURE);
    finish();
    await update;

    expect(host.failed).toHaveBeenCalledTimes(1);
    expect(host.fire).not.toHaveBeenCalled();
  });

  it("fires nothing when the reader left during the reload", async () => {
    const { load, finish, record } = slowLoad();
    const { host, live, mover } = makeMover({ load });
    await mover.move("submit", "Invoice", "INV-1");
    record.docstatus = 1;

    const update = live.send("doc_update", {
      doctype: "Invoice",
      name: "INV-1",
    });
    await vi.waitFor(() => expect(load).toHaveBeenCalled());
    mover.stop();
    finish();
    await update;

    expect(host.fire).not.toHaveBeenCalled();
    expect(live.count()).toBe(0);
  });

  it("hands a failed reload to the host and keeps waiting", async () => {
    const load = vi.fn().mockRejectedValueOnce(new Error("offline"));
    const { host, live, mover, record } = makeMover({ load });
    load.mockResolvedValue(record);
    await mover.move("submit", "Invoice", "INV-1");

    await live.send("doc_update", { doctype: "Invoice", name: "INV-1" });
    expect(host.error).toHaveBeenCalledWith(new Error("offline"));
    record.docstatus = 1;
    await live.send("doc_update", { doctype: "Invoice", name: "INV-1" });

    expect(host.fire).toHaveBeenCalledTimes(1);
  });

  it("does not say 'queued' or fire again when the job finished before the answer", async () => {
    const { host, live, mover, record } = makeMover();
    const moving = mover.move("submit", "Invoice", "INV-1");
    record.docstatus = 1;
    await live.send("doc_update", { doctype: "Invoice", name: "INV-1" });

    await expect(moving).resolves.toEqual({ queued: true });
    expect(host.fire).toHaveBeenCalledTimes(1);
    expect(host.info).not.toHaveBeenCalled();
  });

  it("keeps an unsaved edit: no reload and no after* while the page is dirty", async () => {
    const { host, live, mover } = makeMover({ isDirty: () => true });
    await mover.move("submit", "Invoice", "INV-1");

    await live.send("doc_update", { doctype: "Invoice", name: "INV-1" });

    expect(host.load).not.toHaveBeenCalled();
    expect(host.fire).not.toHaveBeenCalled();
  });

  it("reports a failed job once, fires no after*, and stops listening", async () => {
    const { host, live, mover } = makeMover();
    await mover.move("submit", "Invoice", "INV-1");

    await live.send("submission_failed", { ...FAILURE, ref_docname: "INV-2" });
    expect(host.failed).not.toHaveBeenCalled();
    await live.send("submission_failed", FAILURE);
    await live.send("submission_failed", FAILURE);

    expect(host.failed).toHaveBeenCalledTimes(1);
    expect(host.failed).toHaveBeenCalledWith("submit", FAILURE);
    expect(host.fire).not.toHaveBeenCalled();
    expect(live.count()).toBe(0);
  });

  it("does not say 'queued' when the job failed before the answer came back", async () => {
    const { host, live, mover } = makeMover();
    const moving = mover.move("submit", "Invoice", "INV-1");
    await live.send("submission_failed", FAILURE);

    await expect(moving).resolves.toEqual({ queued: true });

    expect(host.failed).toHaveBeenCalledTimes(1);
    expect(host.info).not.toHaveBeenCalled();
  });

  it("stops listening when the call is refused", async () => {
    server.failure = new Error("Insufficient stock");
    const { live, mover } = makeMover();

    await expect(mover.move("submit", "Invoice", "INV-1")).rejects.toThrow(
      "Insufficient stock",
    );

    expect(live.count()).toBe(0);
  });

  it("hands an after* error to the host", async () => {
    const { host, live, mover, record } = makeMover({
      fire: vi.fn(async () => {
        throw new Error("script broke");
      }),
    });
    await mover.move("submit", "Invoice", "INV-1");

    record.docstatus = 1;
    await live.send("doc_update", { doctype: "Invoice", name: "INV-1" });

    expect(host.error).toHaveBeenCalledWith(new Error("script broke"));
  });
});

describe("the failed-job toast", () => {
  it("names the act and shows the job's error as plain text", () => {
    expect(
      queueFailureMessage("submit", {
        ...FAILURE,
        exception: "Item <b>A</b> not in R&D",
      }),
    ).toBe("Submit failed: Item A not in R&D");
    expect(queueFailureMessage("cancel", FAILURE)).toBe(
      "Cancel failed: Insufficient stock",
    );
  });
});
