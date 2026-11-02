// The Submit and Cancel acts: when each shows, the confirm before it, and the call it sends.
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/i18n", () => ({ __: (text: string, values: string[] = []) => text.replace(/\{(\d)\}/g, (_, i) => values[i] ?? "") }));

// A plain function: a `vi.fn` that rejects reports its own result as an unhandled rejection.
const server = vi.hoisted(() => ({
  calls: [] as unknown[][],
  answer: undefined as unknown,
  failure: undefined as Error | undefined,
  methods: {} as Record<string, unknown>,
}));
vi.mock("@framework/ui/api", () => ({
  runDocumentMethod: async (...call: unknown[]) => {
    server.calls.push(call);
    if (server.failure) throw server.failure;
    return { data: server.answer };
  },
  runMethod: async (method: string, args: unknown) => {
    server.calls.push([method, args]);
    const answer = server.methods[method];
    return { data: typeof answer === "function" ? answer(args) : answer };
  },
  getDocument: async (...call: unknown[]) => {
    server.calls.push(["get", ...call]);
    return { data: server.answer };
  },
}));

import {
  confirmDocstatus,
  docstatusItems,
  isQueued,
  queuedMessage,
  sendDocstatus,
} from "../docstatusActs";

const submittable = { is_submittable: 1 };
const names = (state: Parameters<typeof docstatusItems>[0]) =>
  docstatusItems(state, vi.fn()).map((item) => item.name);

beforeEach(() => {
  server.calls = [];
  server.failure = undefined;
  server.methods = {};
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
  const record = { doctype: "Invoice", name: "INV-1", title: "INV-1" };
  const page = (answer: true | null = true) =>
    ({ dialog: { confirm: vi.fn(async () => answer), danger: vi.fn(async () => answer) } }) as any;
  const LINKED = "frappe.desk.form.linked_with.get_submitted_linked_docs";
  const linked = [
    { doctype: "Payment Entry", name: "PE-1", docstatus: 1 },
    { doctype: "Payment Entry", name: "PE-2", docstatus: 1 },
    { doctype: "Journal Entry", name: "JV-1", docstatus: 1 },
  ];

  it("asks a plain confirm before Submit, naming the record", async () => {
    const current = page();

    const choice = await confirmDocstatus(current, "submit", record);

    expect(choice).toEqual({ all: false });
    expect(current.dialog.confirm).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Submit INV-1?",
        message: "After this, only fields allowed after submit can change.",
      }),
    );
  });

  it("asks a danger confirm before Cancel when no submitted record links to it", async () => {
    server.methods[LINKED] = { docs: [], count: 0, truncated: false };
    const current = page();

    const choice = await confirmDocstatus(current, "cancel", record);

    expect(choice).toEqual({ all: false });
    expect(server.calls[0]).toEqual([LINKED, { doctype: "Invoice", name: "INV-1" }]);
    expect(current.dialog.danger).toHaveBeenCalledWith(
      expect.objectContaining({ title: "Cancel INV-1?", message: "This can't be undone." }),
    );
  });

  it("lists the linked records by DocType and offers Cancel all when the person may cancel them", async () => {
    server.methods[LINKED] = { docs: linked, count: 3, truncated: false };
    server.methods["frappe.client.has_permission"] = { has_permission: true };
    const current = page();

    const choice = await confirmDocstatus(current, "cancel", record);

    expect(choice).toEqual({ all: true, docs: linked });
    expect(current.dialog.danger).toHaveBeenCalledWith(
      expect.objectContaining({
        confirmLabel: "Cancel all",
        message: expect.stringContaining("Payment Entry: PE-1, PE-2; Journal Entry: JV-1"),
      }),
    );
    const checks = server.calls.filter(([method]) => method === "frappe.client.has_permission");
    expect(checks.map(([, args]) => args)).toEqual([
      { doctype: "Payment Entry", docname: "PE-2", perm_type: "cancel" },
      { doctype: "Journal Entry", docname: "JV-1", perm_type: "cancel" },
    ]);
  });

  it("caps the names listed per DocType", async () => {
    const many = Array.from({ length: 12 }, (_, i) => ({ doctype: "Payment Entry", name: `PE-${i + 1}`, docstatus: 1 }));
    server.methods[LINKED] = { docs: many, count: 12, truncated: false };
    server.methods["frappe.client.has_permission"] = { has_permission: true };
    const current = page();

    await confirmDocstatus(current, "cancel", record);

    const { message } = current.dialog.danger.mock.calls[0][0];
    expect(message).toContain("PE-10, and 2 more");
    expect(message).not.toContain("PE-11");
  });

  it("lists them with no Cancel all when the person may not cancel one of the DocTypes", async () => {
    server.methods[LINKED] = { docs: linked, count: 3, truncated: false };
    server.methods["frappe.client.has_permission"] = { has_permission: false };
    const current = page();

    const choice = await confirmDocstatus(current, "cancel", record);

    expect(choice).toBeNull();
    expect(current.dialog.danger).not.toHaveBeenCalled();
    expect(current.dialog.confirm).toHaveBeenCalledWith(
      expect.objectContaining({ message: expect.stringContaining("Journal Entry: JV-1") }),
    );
    expect(current.dialog.confirm.mock.calls[0][0].actions).toEqual([{ label: "Close" }]);
  });

  it("refuses Cancel all when only one of the DocTypes is refused", async () => {
    server.methods[LINKED] = { docs: linked, count: 3, truncated: false };
    server.methods["frappe.client.has_permission"] = ({ doctype }: { doctype: string }) => ({
      has_permission: doctype === "Payment Entry",
    });
    const current = page();

    expect(await confirmDocstatus(current, "cancel", record)).toBeNull();
    expect(current.dialog.danger).not.toHaveBeenCalled();
  });

  it("says the job runs in the background past the listing cap, and sends no list", async () => {
    server.methods[LINKED] = { docs: [], count: 0, truncated: true };
    const current = page();

    const choice = await confirmDocstatus(current, "cancel", record);

    expect(choice).toEqual({ all: true, docs: null });
    expect(current.dialog.danger).toHaveBeenCalledWith(
      expect.objectContaining({ message: expect.stringContaining("in the background"), confirmLabel: "Cancel all" }),
    );
  });

  it("gives null when the person keeps the record", async () => {
    server.methods[LINKED] = { docs: [], count: 0, truncated: false };

    expect(await confirmDocstatus(page(null), "cancel", record)).toBeNull();
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

  it("cancels with the linked records through cancel_all_linked_docs, then reads the record", async () => {
    const docs = [{ doctype: "Payment Entry", name: "PE-1", docstatus: 1 }];
    server.methods["frappe.desk.form.linked_with.cancel_all_linked_docs"] = null;
    server.answer = { name: "INV-1", docstatus: 2 };

    const record = await sendDocstatus("Invoice", "INV-1", "cancel", false, { all: true, docs });

    expect(server.calls[0]).toEqual([
      "frappe.desk.form.linked_with.cancel_all_linked_docs",
      { root_doctype: "Invoice", root_name: "INV-1", docs },
    ]);
    expect(record).toEqual({ name: "INV-1", docstatus: 2 });
  });

  it("sends no list past the cap, and gives null when the server queued the job", async () => {
    server.methods["frappe.desk.form.linked_with.cancel_all_linked_docs"] = { queued: true };

    const record = await sendDocstatus("Invoice", "INV-1", "cancel", false, { all: true, docs: null });

    expect(server.calls).toEqual([
      ["frappe.desk.form.linked_with.cancel_all_linked_docs", { root_doctype: "Invoice", root_name: "INV-1" }],
    ]);
    expect(record).toBeNull();
  });
});

describe("the Submission Queue route", () => {
  it("posts the queue method when the DocType queues in the background", async () => {
    server.answer = { name: "INV-1", docstatus: 0 };

    await sendDocstatus("Invoice", "INV-1", "submit", true);
    await sendDocstatus("Invoice", "INV-1", "cancel", true);

    expect(server.calls.map((call) => call[2])).toEqual(["queue_submit", "queue_cancel"]);
  });

  it("posts the plain method otherwise", async () => {
    await sendDocstatus("Invoice", "INV-1", "submit", false);

    expect(server.calls.map((call) => call[2])).toEqual(["submit"]);
  });

  it("reads a record that did not move as queued", () => {
    expect(isQueued({ docstatus: 0 }, "submit")).toBe(true);
    expect(isQueued({ docstatus: 1 }, "submit")).toBe(false);
    expect(isQueued({ docstatus: 1 }, "cancel")).toBe(true);
    expect(isQueued({ docstatus: 2 }, "cancel")).toBe(false);
  });

  it("names the queued act", () => {
    expect(queuedMessage("submit")).toContain("Queued for Submit");
    expect(queuedMessage("cancel")).toContain("Queued for Cancel");
  });
});
