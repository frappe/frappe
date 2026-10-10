import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, ref } from "vue";
import type { App, Ref } from "vue";
import type { RealtimeSocket } from "../../../socket";
import type { DataImportDoc } from "../types";

interface Call {
  method: string;
  args: Record<string, any>;
}

const PREFIX = "frappe.core.doctype.data_import.data_import.";
const calls: Call[] = [];
// keyed by the method name without the Data Import module prefix
let responders: Record<string, (args: Record<string, any>) => unknown> = {};

vi.mock("frappe-ui", () => ({
  call: (method: string, args: Record<string, any>) => {
    const short = method.replace(PREFIX, "");
    calls.push({ method: short, args });
    const respond = responders[short];
    return Promise.resolve().then(() => (respond ? respond(args) : null));
  },
}));

import { useDataImport, type UseDataImport } from "../useDataImport";

function callsTo(method: string) {
  return calls.filter((c) => c.method === method);
}

async function settle() {
  for (let i = 0; i < 10; i++) {
    await Promise.resolve();
    await nextTick();
  }
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => (resolve = r));
  return { promise, resolve };
}

function serverDoc(overrides: Partial<DataImportDoc> = {}): DataImportDoc {
  return {
    doctype: "Data Import",
    name: "DI-1",
    reference_doctype: "ToDo",
    import_type: "Insert New Records",
    status: "Pending",
    import_file: "/private/files/todo.csv",
    google_sheets_url: null,
    mute_emails: 1,
    submit_after_import: 0,
    use_csv_sniffer: 0,
    custom_delimiters: 0,
    delimiter_options: ",;\\\\t|",
    template_warnings: null,
    value_mappings: [],
    skipped_rows: [],
    ...overrides,
  };
}

const preview = (marker: string) => ({
  columns: [],
  data: [[1, marker]],
  warnings: [],
  import_log: [],
  total_number_of_rows: 1,
});

function fakeSocket() {
  const emitted: unknown[][] = [];
  const listeners = new Map<string, Set<(...args: unknown[]) => void>>();
  const socket: RealtimeSocket = {
    emit: (event, ...args) => emitted.push([event, ...args]),
    on: (event, handler) => {
      if (!listeners.has(event)) listeners.set(event, new Set());
      listeners.get(event)!.add(handler);
    },
    off: (event, handler) => listeners.get(event)?.delete(handler),
  };
  const fire = (event: string, payload: unknown) =>
    listeners.get(event)?.forEach((handler) => handler(payload));
  const count = (event: string) => listeners.get(event)?.size ?? 0;
  return { socket, emitted, fire, count };
}

let app: App | undefined;
let host: HTMLElement | undefined;
let live: ReturnType<typeof fakeSocket>;

function mount(
  name: Ref<string | null>,
  options?: Parameters<typeof useDataImport>[1]
) {
  let result!: UseDataImport;
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({
    setup() {
      result = useDataImport(name, options);
      return () => h("div");
    },
  });
  app.provide("socket", live.socket);
  app.mount(host);
  return result;
}

beforeEach(() => {
  calls.length = 0;
  live = fakeSocket();
  responders = {
    "frappe.client.get": (args) => serverDoc({ name: args.name }),
    get_preview_from_template: (args) => preview(args.data_import),
    get_import_fields: () => null,
    "frappe.desk.form.load.getdoctype": (args) => ({
      docs: [{ name: args.doctype, fields: [] }],
    }),
  };
});

afterEach(() => {
  app?.unmount();
  host?.remove();
  app = undefined;
  host = undefined;
  vi.restoreAllMocks();
});

describe("useDataImport: a new import", () => {
  it("reads a doctype getter again when it goes back to a new import", async () => {
    const name = ref<string | null>("DI-1");
    const doctype = ref<string | undefined>(undefined);
    const di = mount(name, { doctype: () => doctype.value });
    await settle();

    doctype.value = "CRM Deal";
    name.value = null;
    await settle();
    expect(di.isNew.value).toBe(true);
    expect(di.doc.value.reference_doctype).toBe("CRM Deal");
  });

  it("holds an unsaved doc with Desk's defaults and calls nothing for it", async () => {
    const name = ref<string | null>(null);
    const di = mount(name, { doctype: "ToDo" });
    di.doc.value.import_type = "Update Existing Records";
    await settle();

    expect(di.isNew.value).toBe(true);
    expect(di.doc.value).toMatchObject({
      doctype: "Data Import",
      reference_doctype: "ToDo",
      status: "Pending",
    });
    expect(callsTo("frappe.client.get")).toHaveLength(0);
    expect(callsTo("frappe.client.insert")).toHaveLength(0);
    expect(callsTo("get_preview_from_template")).toHaveLength(0);
    expect(live.emitted).toEqual([]);
  });

  it("inserts on the first save, sets the name and keeps the doc instead of reloading", async () => {
    responders["frappe.client.insert"] = (args) =>
      serverDoc({ ...args.doc, name: "DI-NEW" });
    const name = ref<string | null>(null);
    const di = mount(name, { doctype: "ToDo" });
    di.doc.value.import_file = "/private/files/todo.csv";

    await di.save();
    await settle();

    expect(callsTo("frappe.client.insert")[0].args.doc).toMatchObject({
      doctype: "Data Import",
      reference_doctype: "ToDo",
      import_type: "Insert New Records",
      import_file: "/private/files/todo.csv",
    });
    expect(name.value).toBe("DI-NEW");
    expect(di.isNew.value).toBe(false);
    expect(di.dirty.value).toBe(false);
    expect(callsTo("frappe.client.get")).toHaveLength(0);
    expect(callsTo("get_preview_from_template")[0].args).toEqual({
      data_import: "DI-NEW",
      import_file: "/private/files/todo.csv",
      google_sheets_url: null,
    });
    expect(di.previewReady.value).toBe(true);
    expect(live.emitted).toEqual([["doc_subscribe", "Data Import", "DI-NEW"]]);
  });
});

describe("useDataImport: an existing import", () => {
  it("loads the doc and its preview", async () => {
    const di = mount(ref("DI-1"));
    await settle();

    expect(callsTo("frappe.client.get")[0].args).toEqual({
      doctype: "Data Import",
      name: "DI-1",
    });
    expect(di.doc.value.name).toBe("DI-1");
    expect(di.dirty.value).toBe(false);
    expect(di.preview.value?.data).toEqual([[1, "DI-1"]]);
    expect(di.previewReady.value).toBe(true);
  });

  it("defaults values the server can create to being created, as an unsaved edit", async () => {
    const mapping = {
      column: 2,
      fieldname: "organization",
      fieldtype: "Link" as const,
      link_doctype: "CRM Organization",
      source_value: "Northwind",
      target_value: "",
    };
    responders["frappe.client.get"] = (args) =>
      serverDoc({
        name: args.name,
        value_mappings: [
          { ...mapping, can_create: 1, create_new: 0 },
          {
            ...mapping,
            source_value: "Mapped",
            can_create: 1,
            target_value: "Acme",
          },
          {
            ...mapping,
            source_value: "Nope",
            link_doctype: "User",
            can_create: 0,
          },
        ],
      });
    const di = mount(ref("DI-1"));
    await settle();

    expect(di.doc.value.value_mappings.map((m) => m.create_new)).toEqual([
      1,
      undefined,
      undefined,
    ]);
    expect(di.dirty.value).toBe(true);
  });

  it("marks edits dirty, saves the whole doc, takes the server's copy and refetches the preview", async () => {
    responders["frappe.client.get"] = () =>
      serverDoc({
        template_warnings: '[{"row": 2}]',
        value_mappings: [
          {
            source_value: "Hgh",
            column: 1,
            fieldname: "priority",
            fieldtype: "Select",
            target_value: null,
          },
        ],
      });
    responders["frappe.client.save"] = (args) =>
      serverDoc({ ...args.doc, template_warnings: "" });
    const di = mount(ref("DI-1"));
    await settle();
    expect(callsTo("get_preview_from_template")).toHaveLength(1);

    di.doc.value.value_mappings[0].target_value = "High";
    di.doc.value.skipped_rows.push({ row_number: 3, row_data: "[]" });
    expect(di.dirty.value).toBe(true);

    await di.save();
    await settle();

    const sent = callsTo("frappe.client.save")[0].args.doc;
    expect(sent.value_mappings[0].target_value).toBe("High");
    expect(sent.skipped_rows).toEqual([{ row_number: 3, row_data: "[]" }]);
    expect(sent.import_file).toBe("/private/files/todo.csv");
    expect(di.doc.value.template_warnings).toBe("");
    expect(di.dirty.value).toBe(false);
    expect(callsTo("get_preview_from_template")).toHaveLength(2);
  });

  it("does not refetch the preview after saving an import that has started", async () => {
    responders["frappe.client.get"] = () => serverDoc({ status: "Success" });
    responders["frappe.client.save"] = (args) => serverDoc(args.doc);
    const di = mount(ref("DI-1"));
    await settle();
    const before = callsTo("get_preview_from_template").length;

    await di.save();
    await settle();

    expect(callsTo("get_preview_from_template")).toHaveLength(before);
  });

  it("exposes a failed preview's message and does not fetch it again on reload", async () => {
    responders.get_preview_from_template = () => {
      throw Object.assign(new Error("x"), { messages: ["Bad file"] });
    };
    const di = mount(ref("DI-1"));
    await settle();
    expect(di.previewError.value).toBe("Bad file");
    expect(di.previewReady.value).toBe(false);

    await di.reload();
    await settle();
    expect(callsTo("get_preview_from_template")).toHaveLength(1);

    await di.fetchPreview({ force: true });
    expect(callsTo("get_preview_from_template")).toHaveLength(2);
  });
});

describe("useDataImport: stale previews", () => {
  it("ignores a delayed preview for an import that is no longer open", async () => {
    const slowA = deferred<unknown>();
    responders.get_preview_from_template = (args) =>
      args.data_import === "DI-A" ? slowA.promise : preview("B");
    const name = ref<string | null>("DI-A");
    const di = mount(name);
    await settle();
    expect(callsTo("get_preview_from_template")).toHaveLength(1);

    name.value = "DI-B";
    await settle();
    expect(di.preview.value?.data).toEqual([[1, "B"]]);

    slowA.resolve(preview("A"));
    await settle();
    expect(di.doc.value.name).toBe("DI-B");
    expect(di.preview.value?.data).toEqual([[1, "B"]]);
  });

  it("ignores a response older than the latest request", async () => {
    const first = deferred<unknown>();
    let n = 0;
    const di = mount(ref("DI-1"));
    await settle();
    responders.get_preview_from_template = () =>
      ++n === 1 ? first.promise : preview("second");

    di.fetchPreview({ force: true });
    await di.fetchPreview({ force: true });
    first.resolve(preview("first"));
    await settle();

    expect(di.preview.value?.data).toEqual([[1, "second"]]);
    expect(di.previewLoading.value).toBe(false);
  });

  it("drops the old import's state when another one is opened", async () => {
    responders["frappe.client.get"] = (args) =>
      args.name === "DI-A"
        ? serverDoc({ name: "DI-A", status: "Success" })
        : new Promise(() => {});
    responders.get_import_logs = () => [{ success: 1 }];
    const name = ref<string | null>("DI-A");
    const di = mount(name);
    await settle();
    expect(di.logs.value).toHaveLength(1);

    name.value = "DI-B";
    await settle();
    expect(di.doc.value.name).toBeUndefined();
    expect(di.preview.value).toBeNull();
    expect(di.logs.value).toEqual([]);
    expect(di.importStatus.value).toBeNull();
  });
});

describe("useDataImport: realtime", () => {
  it("joins the import's room, moves with the name and leaves on unmount", async () => {
    const name = ref<string | null>("DI-A");
    mount(name);
    await settle();
    expect(live.emitted).toEqual([["doc_subscribe", "Data Import", "DI-A"]]);

    name.value = "DI-B";
    await settle();
    expect(live.emitted.slice(1)).toEqual([
      ["doc_unsubscribe", "Data Import", "DI-A"],
      ["doc_subscribe", "Data Import", "DI-B"],
    ]);
    expect(live.count("data_import_progress")).toBe(1);

    app!.unmount();
    app = undefined;
    expect(live.emitted.at(-1)).toEqual([
      "doc_unsubscribe",
      "Data Import",
      "DI-B",
    ]);
    expect(live.count("data_import_progress")).toBe(0);
    expect(live.count("data_import_refresh")).toBe(0);
    expect(live.count("data_import_blocked")).toBe(0);
  });

  it("applies progress for this import only, keeps missing counts and collapses repeated activity", async () => {
    const di = mount(ref("DI-1"));
    await settle();

    live.fire("data_import_progress", {
      data_import: "OTHER",
      current: 1,
      total: 9,
    });
    expect(di.progress.value).toBeNull();
    expect(di.running.value).toBe(false);

    const activity = { kind: "success", text: "Inserted ToDo 1" };
    live.fire("data_import_progress", {
      data_import: "DI-1",
      current: 1,
      total: 9,
      eta: 12.7,
      inserted: 1,
      updated: 0,
      failed: 0,
      row_indexes: [2],
      activity,
    });
    live.fire("data_import_progress", {
      data_import: "DI-1",
      current: 2,
      total: 9,
      eta: 10,
      activity,
    });
    for (let i = 0; i < 6; i++)
      live.fire("data_import_progress", {
        data_import: "DI-1",
        current: 3 + i,
        total: 9,
        activity: { text: `row ${i}` },
      });

    expect(di.running.value).toBe(true);
    expect(di.progress.value).toMatchObject({
      current: 8,
      total: 9,
      inserted: 1,
      updated: 0,
      failed: 0,
    });
    const texts = di.progress.value!.recentActivity.map((a) => a.text);
    expect(texts).toEqual(["row 5", "row 4", "row 3", "row 2", "row 1"]);
  });

  it("keeps one entry for a repeated activity and reads its row", async () => {
    const di = mount(ref("DI-1"));
    await settle();
    const event = {
      data_import: "DI-1",
      current: 1,
      total: 9,
      eta: 12.7,
      row_indexes: [4],
      activity: { kind: "success", text: "Inserted" },
    };
    live.fire("data_import_progress", event);
    live.fire("data_import_progress", { ...event, current: 2 });

    expect(di.progress.value!.eta).toBe(12);
    expect(di.progress.value!.recentActivity).toEqual([
      { kind: "success", text: "Inserted", isHtml: false, row: 4 },
    ]);
  });

  it("reloads on refresh for this import only and stops the progress", async () => {
    const di = mount(ref("DI-1"));
    await settle();
    live.fire("data_import_progress", {
      data_import: "DI-1",
      current: 1,
      total: 9,
    });

    live.fire("data_import_refresh", { data_import: "OTHER" });
    await settle();
    expect(callsTo("frappe.client.get")).toHaveLength(1);

    responders["frappe.client.get"] = () => serverDoc({ status: "Success" });
    live.fire("data_import_refresh", { data_import: "DI-1" });
    await settle();
    expect(callsTo("frappe.client.get")).toHaveLength(2);
    expect(di.progress.value).toBeNull();
    expect(di.running.value).toBe(false);
    expect(callsTo("get_import_logs")).toHaveLength(1);
  });

  it("reloads on blocked for this import only, then raises the blocked signal", async () => {
    const di = mount(ref("DI-1"));
    await settle();

    live.fire("data_import_blocked", { data_import: "OTHER" });
    await settle();
    expect(di.blocked.value).toBe(false);
    expect(callsTo("frappe.client.get")).toHaveLength(1);

    responders["frappe.client.get"] = () =>
      serverDoc({ template_warnings: '[{"row": 2}]' });
    live.fire("data_import_blocked", { data_import: "DI-1" });
    await settle();
    expect(callsTo("frappe.client.get")).toHaveLength(2);
    expect(di.doc.value.template_warnings).toBe('[{"row": 2}]');
    expect(di.blocked.value).toBe(true);
  });
});

describe("useDataImport: status, progress counts and logs", () => {
  it("fetches no status while Pending", async () => {
    mount(ref("DI-1"));
    await settle();
    expect(callsTo("get_import_status")).toHaveLength(0);
    expect(callsTo("get_import_logs")).toHaveLength(0);
  });

  it("fetches progress counts while In Progress, at most once every 2s", async () => {
    let now = 10_000;
    vi.spyOn(Date, "now").mockImplementation(() => now);
    responders["frappe.client.get"] = () =>
      serverDoc({ status: "In Progress" });
    responders.get_import_status = () => ({
      status: "In Progress",
      total_records: 50,
      processed_records: 20,
      success: 18,
      failed: 2,
    });
    const di = mount(ref("DI-1"));
    await settle();

    expect(callsTo("get_import_status")).toHaveLength(1);
    expect(callsTo("get_import_logs")).toHaveLength(0);
    expect(di.running.value).toBe(true);
    expect(di.progress.value).toMatchObject({
      current: 20,
      total: 50,
      inserted: 18,
      failed: 2,
    });

    now += 1000;
    await di.reload();
    await settle();
    expect(callsTo("get_import_status")).toHaveLength(1);

    now += 1500;
    await di.reload();
    await settle();
    expect(callsTo("get_import_status")).toHaveLength(2);
  });

  it("loads the status summary then the logs for the filter once finished", async () => {
    responders["frappe.client.get"] = () =>
      serverDoc({ status: "Partial Success" });
    responders.get_import_status = () => ({
      status: "Partial Success",
      total_records: 2400,
      success: 2000,
      failed: 400,
    });
    responders.get_import_logs = (args) =>
      args.status === "failed"
        ? [{ success: 0 }]
        : [{ success: 1 }, { success: 0 }];
    const di = mount(ref("DI-1"));
    await settle();

    expect(di.importStatus.value?.success).toBe(2000);
    expect(callsTo("get_import_logs")[0].args).toEqual({
      data_import: "DI-1",
      status: "all",
    });
    expect(di.logs.value).toHaveLength(2);

    di.logFilter.value = "failed";
    await settle();
    expect(callsTo("get_import_logs")[1].args.status).toBe("failed");
    expect(di.logs.value).toEqual([{ success: 0 }]);
  });
});

describe("useDataImport: start and stop", () => {
  it("counts as running from Start until the server answers", async () => {
    const answer = deferred<boolean>();
    responders.form_start_import = () => answer.promise;
    const di = mount(ref("DI-1"));
    await settle();

    const started = di.start();
    expect(di.running.value).toBe(true);
    expect(di.progress.value).toMatchObject({ current: 0, total: 0 });
    answer.resolve(true);

    expect(await started).toBe(true);
    expect(callsTo("form_start_import")[0].args).toEqual({
      data_import: "DI-1",
    });
  });

  it("stops the job and reloads", async () => {
    responders.stop_data_import = () => ({
      status: "not_running",
      message: "Job was not running; status updated.",
    });
    const di = mount(ref("DI-1"));
    await settle();

    const response = await di.stop();
    expect(callsTo("stop_data_import")[0].args).toEqual({ doc_name: "DI-1" });
    expect(response?.status).toBe("not_running");
    expect(callsTo("frappe.client.get")).toHaveLength(2);
  });
});

describe("useDataImport: import fields", () => {
  it("loads the DocType's meta next to the provider's schema", async () => {
    responders.get_import_fields = () => ({ fields: [{ fieldname: "x" }] });
    const di = mount(ref(null), { doctype: "ToDo" });
    await settle();
    expect(di.providerSchema.value).toEqual({ fields: [{ fieldname: "x" }] });
    expect(di.doctypeMeta.value).toEqual([{ name: "ToDo", fields: [] }]);
  });

  it("loads only the DocType's meta when there is no provider schema", async () => {
    const di = mount(ref(null), { doctype: "ToDo" });
    await settle();
    expect(callsTo("get_import_fields")[0].args).toEqual({ doctype: "ToDo" });
    expect(callsTo("frappe.desk.form.load.getdoctype")[0].args).toEqual({
      doctype: "ToDo",
      with_parent: 1,
    });
    expect(di.providerSchema.value).toBeNull();
    expect(di.doctypeMeta.value).toEqual([{ name: "ToDo", fields: [] }]);
  });

  it("drops a meta answer for a DocType that is no longer chosen", async () => {
    const todoMeta = deferred<unknown>();
    responders["frappe.desk.form.load.getdoctype"] = (args) =>
      args.doctype === "ToDo"
        ? todoMeta.promise
        : { docs: [{ name: args.doctype, fields: [] }] };
    const di = mount(ref(null), { doctype: "ToDo" });
    await settle();
    di.doc.value.reference_doctype = "Note";
    await settle();
    todoMeta.resolve({ docs: [{ name: "ToDo", fields: [] }] });
    await settle();
    expect(di.doctypeMeta.value).toEqual([{ name: "Note", fields: [] }]);
  });
});
