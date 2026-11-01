// The Submit and Cancel acts: when each shows, the confirm before it, and the call it sends.
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/i18n", () => ({ __: (text: string, values: string[] = []) => text.replace("{0}", values[0] ?? "") }));

// A plain function: a `vi.fn` that rejects reports its own result as an unhandled rejection.
const server = vi.hoisted(() => ({
  calls: [] as unknown[][],
  answer: undefined as unknown,
  failure: undefined as Error | undefined,
}));
vi.mock("@framework/ui/api", () => ({
  runDocumentMethod: async (...call: unknown[]) => {
    server.calls.push(call);
    if (server.failure) throw server.failure;
    return { data: server.answer };
  },
}));

import { confirmDocstatus, docstatusItems, sendDocstatus } from "../docstatusActs";

const submittable = { is_submittable: 1 };
const names = (state: Parameters<typeof docstatusItems>[0]) =>
  docstatusItems(state, vi.fn()).map((item) => item.name);

beforeEach(() => {
  server.calls = [];
  server.failure = undefined;
});

describe("docstatusItems", () => {
  it("offers Submit on a clean saved draft of a submittable doctype", () => {
    const [submit] = docstatusItems({ meta: submittable, saved: { docstatus: 0 }, dirty: false, canWrite: true }, vi.fn());

    expect(submit).toMatchObject({ name: "submit", right: "submit", display: "button" });
  });

  it("offers neither on a draft with unsaved changes", () => {
    expect(names({ meta: submittable, saved: { docstatus: 0 }, dirty: true, canWrite: true })).toEqual([]);
  });

  it("offers Cancel in the danger group of a clean submitted record, and not with unsaved changes", () => {
    const [cancel, ...rest] = docstatusItems({ meta: submittable, saved: { docstatus: 1 }, dirty: false, canWrite: true }, vi.fn());

    expect(cancel).toMatchObject({ name: "cancel", right: "cancel", group: "danger" });
    expect(rest).toEqual([]);
    expect(names({ meta: submittable, saved: { docstatus: 1 }, dirty: true, canWrite: true })).toEqual([]);
  });

  it("offers neither without the write right, which the server's call also needs", () => {
    expect(names({ meta: submittable, saved: { docstatus: 0 }, dirty: false, canWrite: false })).toEqual([]);
    expect(names({ meta: submittable, saved: { docstatus: 1 }, dirty: false, canWrite: false })).toEqual([]);
  });

  it("offers neither on a cancelled record", () => {
    expect(names({ meta: submittable, saved: { docstatus: 2 }, dirty: false, canWrite: true })).toEqual([]);
  });

  it("offers neither on a doctype that cannot submit", () => {
    expect(names({ meta: { is_submittable: 0 }, saved: { docstatus: 0 }, dirty: false, canWrite: true })).toEqual([]);
    expect(names({ meta: null, saved: { docstatus: 0 }, dirty: false, canWrite: true })).toEqual([]);
  });

  it("offers neither under an active workflow", () => {
    const meta = { ...submittable, workflow_state_field: "workflow_state" };
    expect(names({ meta, saved: { docstatus: 0 }, dirty: false, canWrite: true })).toEqual([]);
    expect(names({ meta, saved: { docstatus: 1 }, dirty: false, canWrite: true })).toEqual([]);
  });

  it("runs its act when the item runs", () => {
    const run = vi.fn();
    const [submit] = docstatusItems({ meta: submittable, saved: { docstatus: 0 }, dirty: false, canWrite: true }, run);
    const [cancel] = docstatusItems({ meta: submittable, saved: { docstatus: 1 }, dirty: false, canWrite: true }, run);

    submit.run!({} as any);
    cancel.run!({} as any);

    expect(run.mock.calls).toEqual([["submit"], ["cancel"]]);
  });
});

describe("confirmDocstatus", () => {
  const page = () => ({ dialog: { confirm: vi.fn(async () => true), danger: vi.fn(async () => true) } }) as any;

  it("asks a plain confirm before Submit, naming the record", async () => {
    const current = page();

    await confirmDocstatus(current, "submit", "INV-1");

    expect(current.dialog.confirm).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Submit INV-1?",
        message: "After this, only fields allowed after submit can change.",
      }),
    );
  });

  it("asks a danger confirm before Cancel, naming the record", async () => {
    const current = page();

    await confirmDocstatus(current, "cancel", "INV-1");

    expect(current.dialog.danger).toHaveBeenCalledWith(
      expect.objectContaining({ title: "Cancel INV-1?", message: "This can't be undone." }),
    );
  });
});

describe("sendDocstatus", () => {
  it("posts the named method and gives the record the server holds", async () => {
    server.answer = { name: "INV-1", docstatus: 1 };

    const record = await sendDocstatus("Invoice", "INV-1", "submit");

    expect(server.calls).toEqual([["Invoice", "INV-1", "submit"]]);
    expect(record).toEqual({ name: "INV-1", docstatus: 1 });
  });

  it("rejects with the server's message as text, tags removed", async () => {
    server.failure = new Error("<b>Insufficient</b> stock<br>for SKU010");

    await expect(sendDocstatus("Invoice", "INV-1", "cancel")).rejects.toThrow("Insufficient stock for SKU010");
  });
});
