import { afterEach, describe, expect, it, vi } from "vitest";
import { computed, createApp, h, nextTick, ref } from "vue";
import type { App } from "vue";
import DataImportWizard from "../DataImportWizard.vue";
import ImportStatus from "../ImportStatus.vue";
import ImportStep from "../steps/ImportStep.vue";
import type {
  DataImportDoc,
  DataImportLog,
  DataImportLogFilter,
  DataImportProgress,
  DataImportStatusSummary,
} from "../types";
import type { UseDataImport } from "../useDataImport";

const { callMock } = vi.hoisted(() => ({
  callMock: vi.fn(async (): Promise<unknown> => []),
}));

vi.mock("frappe-ui", async (importOriginal) => ({
  ...(await importOriginal<typeof import("frappe-ui")>()),
  call: callMock,
}));

let app: App | undefined;
let host: HTMLElement | undefined;

afterEach(() => {
  app?.unmount();
  host?.remove();
  document.body.innerHTML = "";
  app = undefined;
  host = undefined;
  vi.restoreAllMocks();
});

function savedDoc(overrides: Partial<DataImportDoc> = {}): DataImportDoc {
  return {
    doctype: "Data Import",
    name: "DI-1",
    reference_doctype: "ToDo",
    import_type: "Insert New Records",
    status: "Partial Success",
    import_file: "/private/files/todo.csv",
    mute_emails: 1,
    submit_after_import: 0,
    use_csv_sniffer: 0,
    custom_delimiters: 0,
    value_mappings: [],
    skipped_rows: [],
    owner: "admin@example.com",
    modified_by: "jane@example.com",
    ...overrides,
  };
}

interface FakeState {
  doc?: Partial<DataImportDoc>;
  running?: boolean;
  progress?: Partial<DataImportProgress> | null;
  importStatus?: DataImportStatusSummary | null;
  logs?: DataImportLog[];
}

function fakeDataImport(state: FakeState = {}) {
  const doc = ref(savedDoc(state.doc));
  const running = ref(!!state.running);
  return {
    doc,
    running,
    importStarted: computed(
      () => running.value || doc.value.status !== "Pending"
    ),
    progress: ref<DataImportProgress | null>(
      state.progress === null || state.progress === undefined
        ? null
        : {
            current: 0,
            total: 0,
            eta: 0,
            inserted: 0,
            updated: 0,
            failed: 0,
            skipping: false,
            recentActivity: [],
            ...state.progress,
          }
    ),
    importStatus: ref<DataImportStatusSummary | null>(
      state.importStatus === undefined
        ? { status: doc.value.status, total_records: 3, success: 2, failed: 1 }
        : state.importStatus
    ),
    logFilter: ref<DataImportLogFilter>("all"),
    logs: ref<DataImportLog[]>(state.logs ?? []),
  };
}

function mount(component: unknown, state: FakeState = {}) {
  const fake = fakeDataImport(state);
  const onOpenList = vi.fn();
  const onOpenRecord = vi.fn();
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({
    render: () =>
      h(component as any, {
        dataImport: fake as unknown as UseDataImport,
        onOpenList,
        onOpenRecord,
      }),
  });
  app.mount(host);
  return { fake, onOpenList, onOpenRecord };
}

// Text nodes joined by spaces, so adjacent elements don't run together.
function text() {
  const walker = document.createTreeWalker(host!, NodeFilter.SHOW_TEXT);
  const parts: string[] = [];
  while (walker.nextNode()) parts.push(walker.currentNode.textContent!.trim());
  return parts.filter(Boolean).join(" ").replace(/\s+/g, " ");
}

function button(label: string) {
  const found = [...host!.querySelectorAll("button")].find(
    (b) =>
      b.textContent?.trim().startsWith(label) ||
      b.getAttribute("aria-label") === label
  );
  if (!found) throw new Error(`no "${label}" button`);
  return found;
}

const successLog = (row: number, docname: string): DataImportLog => ({
  success: 1,
  docname,
  row_indexes: JSON.stringify([row]),
});

describe("ImportStep while running", () => {
  it("shows row progress, counts and recent activity from progress", () => {
    mount(ImportStep, {
      running: true,
      doc: {
        status: "In Progress",
        skipped_rows: [{ row_number: 9, row_data: "[]" }],
      },
      progress: {
        current: 25,
        total: 100,
        eta: 90,
        inserted: 20,
        failed: 5,
        recentActivity: [
          { kind: "success", text: "Inserted TD-1", isHtml: false, row: 25 },
          { kind: "error", text: "Missing title", isHtml: false, row: 24 },
        ],
      },
    });
    const page = text();
    expect(page).toContain("Importing your data");
    expect(page).toContain("Importing row 25 of 100");
    expect(page).toContain("25%");
    expect(page).toContain("About 1 minute remaining");
    expect(page).toContain("Inserted 20");
    expect(page).not.toContain("Updated");
    expect(page).toContain("Skipped 1");
    expect(page).toContain("Failed 5");
    expect(page).toContain("Inserted TD-1");
    expect(page).toContain("Row 24");
    expect(host!.querySelector(".lucide-circle-check")).not.toBeNull();
    expect(host!.querySelector(".lucide-circle-alert")).not.toBeNull();
  });

  it("says Finishing up once every row is done", () => {
    mount(ImportStep, {
      running: true,
      doc: { status: "In Progress" },
      progress: { current: 10, total: 10 },
    });
    expect(text()).toContain("Finishing up...");
  });

  it("shows the starting state before any progress arrives", () => {
    mount(ImportStep, {
      running: true,
      doc: { status: "Pending" },
      progress: {},
    });
    expect(text()).toContain("Starting import...");
    expect(text()).toContain("Preparing import...");
    expect(text()).toContain("Live activity updates will appear here.");
  });

  it("shows Updated, not Inserted, for Update Existing Records", () => {
    mount(ImportStep, {
      running: true,
      doc: { status: "In Progress", import_type: "Update Existing Records" },
      progress: { current: 1, total: 10, updated: 1 },
    });
    expect(text()).toContain("Updated 1");
    expect(text()).not.toContain("Inserted");
  });
});

describe("ImportStep result", () => {
  it("shows the result counts and details", () => {
    mount(ImportStep, { logs: [successLog(1, "TD-1")] });
    const page = text();
    expect(page).toContain("Total rows 3");
    expect(page).toContain("Inserted 2");
    expect(page).toContain("Skipped 0");
    expect(page).toContain("Failed 1");
    expect(page).toContain("Started by admin@example.com");
    expect(page).toContain("Last modified by jane@example.com");
  });

  it("shows who started the import by full name, as a link to the user", async () => {
    callMock.mockResolvedValueOnce([
      { name: "admin@example.com", full_name: "Admin User" },
      { name: "jane@example.com", full_name: "Jane Doe" },
    ]);
    const { onOpenRecord } = mount(ImportStep, {
      logs: [successLog(1, "TD-1")],
    });
    await new Promise((resolve) => setTimeout(resolve));
    await nextTick();
    expect(callMock).toHaveBeenCalledWith("frappe.client.get_list", {
      doctype: "User",
      fields: ["name", "full_name"],
      filters: { name: ["in", ["admin@example.com", "jane@example.com"]] },
    });
    expect(text()).toContain("Started by Admin User");
    expect(text()).toContain("Last modified by Jane Doe");
    const link = [...document.querySelectorAll("button")].find(
      (b) => b.textContent?.trim() === "Admin User"
    )!;
    link.click();
    expect(onOpenRecord).toHaveBeenCalledWith("User", "admin@example.com");
  });

  it("counts inserted and updated for an upsert", () => {
    mount(ImportStep, {
      doc: { import_type: "Insert or Update Records" },
      importStatus: {
        status: "Success",
        total_records: 5,
        success: 5,
        inserted: 3,
        updated: 2,
      },
    });
    expect(text()).toContain("Inserted 3");
    expect(text()).toContain("Updated 2");
  });

  it("log filter tabs set logFilter", async () => {
    const { fake } = mount(ImportStep);
    expect(text()).toContain("All (3)");
    expect(text()).toContain("Success (2)");
    expect(text()).toContain("Failed (1)");
    button("Failed (1)").click();
    await nextTick();
    expect(fake.logFilter.value).toBe("failed");
    expect(text()).toContain("No failed log entries");
  });

  it("shows 1000 of N and Export Import Log when the log is cut off", () => {
    mount(ImportStep, {
      importStatus: { status: "Success", total_records: 1500, success: 1500 },
    });
    expect(text()).toContain("All (1000 of 1500)");
    expect(text()).toContain("Export Import Log");
  });

  it("expands a failed row to show extra messages, not the traceback", async () => {
    mount(ImportStep, {
      logs: [
        {
          success: 0,
          row_indexes: "[3]",
          messages: JSON.stringify([
            { message: "Title is required" },
            { title: "Hint", message: "Fill the title column" },
          ]),
          exception: "Traceback: boom",
        },
      ],
    });
    expect(text()).toContain("Title is required");
    expect(text()).toContain("Failure");
    expect(text()).not.toContain("Traceback: boom");
    button("Toggle error details").click();
    await nextTick();
    expect(text()).toContain("Fill the title column");
    expect(host!.querySelector("pre")).toBeNull();
  });

  it("shows the traceback for a failure with no message", async () => {
    mount(ImportStep, {
      logs: [
        {
          success: 0,
          row_indexes: "[3]",
          messages: "[]",
          exception: "Traceback: boom",
        },
      ],
    });
    expect(text()).toContain("Import failed");
    button("Toggle error details").click();
    await nextTick();
    expect(host!.querySelector("pre")?.textContent).toContain(
      "Traceback: boom"
    );
  });

  it("Go to list and a record name emit the events", () => {
    const { onOpenList, onOpenRecord } = mount(ImportStep, {
      logs: [successLog(1, "TD-1")],
    });
    expect(text()).toContain("Successfully imported TD-1");
    expect(button("TD-1").textContent).toBe("TD-1");
    button("Go to list").click();
    expect(onOpenList).toHaveBeenCalledWith("ToDo");
    button("TD-1").click();
    expect(onOpenRecord).toHaveBeenCalledWith("ToDo", "TD-1");
  });

  it("offers Go to list after a failed import too", () => {
    mount(ImportStep, { doc: { status: "Error" } });
    expect(button("Go to list")).toBeTruthy();
  });

  it("downloads post a form to the right method with the import's name", () => {
    (globalThis as any).csrf_token = "tok";
    const posted: { action: string; fields: Record<string, string> }[] = [];
    vi.spyOn(HTMLFormElement.prototype, "submit").mockImplementation(function (
      this: HTMLFormElement
    ) {
      const fields: Record<string, string> = {};
      for (const field of this.querySelectorAll("textarea"))
        fields[field.name] = field.value;
      posted.push({ action: this.getAttribute("action")!, fields });
    });
    mount(ImportStep, {
      doc: { skipped_rows: [{ row_number: 2, row_data: "[]" }] },
      importStatus: {
        status: "Success",
        total_records: 1500,
        success: 1499,
        failed: 1,
      },
    });
    button("Download Skipped Rows").click();
    button("Download Failed Rows").click();
    button("Export Import Log").click();
    const base = "/api/method/frappe.core.doctype.data_import.data_import.";
    expect(posted.map((p) => p.action)).toEqual([
      base + "download_skipped_rows",
      base + "download_errored_template",
      base + "download_import_log",
    ]);
    for (const p of posted)
      expect(p.fields).toEqual({ data_import_name: "DI-1", csrf_token: "tok" });
    expect(document.querySelector("form")).toBeNull();
    delete (globalThis as any).csrf_token;
  });
});

describe("ImportStatus", () => {
  it("shows Desk's headline with the failed and skipped hints", () => {
    mount(ImportStatus, {
      doc: { skipped_rows: [{ row_number: 2, row_data: "[]" }] },
    });
    expect(text()).toContain("Successfully imported 2 out of 3 records.");
    expect(text()).toContain("Use 'Download Failed Rows' on the Failed metric");
    expect(text()).toContain(
      "Use 'Download Skipped Rows' on the Skipped metric"
    );
  });

  it("uses the upsert headline and the timed out hint", () => {
    mount(ImportStatus, {
      doc: { import_type: "Insert or Update Records", status: "Timed Out" },
      importStatus: {
        status: "Timed Out",
        total_records: 4,
        success: 3,
        inserted: 1,
        updated: 2,
      },
    });
    expect(text()).toContain(
      "Successfully inserted 1 and updated 2 out of 4 records."
    );
    expect(text()).toContain("Import timed out, please re-try.");
  });

  it("shows nothing for a pending import", () => {
    mount(ImportStatus, { doc: { status: "Pending" }, importStatus: null });
    expect(text().trim()).toBe("");
  });

  it("shows import progress while running", () => {
    mount(ImportStatus, {
      running: true,
      doc: { status: "In Progress" },
      importStatus: null,
      progress: { current: 5, total: 10, eta: 30 },
    });
    expect(text()).toContain("Import Progress");
    expect(text()).toContain("Importing 5 of 10, About 30 seconds remaining");
  });
});

describe("DataImportWizard with the Import step", () => {
  function mountWizard(state: FakeState) {
    const fake = fakeDataImport(state);
    const wizardFake = {
      ...fake,
      isNew: computed(() => false),
      dirty: computed(() => false),
      loading: ref(false),
      saving: ref(false),
      hasImportFile: computed(() => true),
      previewReady: ref(true),
      previewLoading: ref(false),
      previewError: ref(null),
      blocked: ref(false),
    };
    const onOpenList = vi.fn();
    const onOpenRecord = vi.fn();
    host = document.createElement("div");
    document.body.appendChild(host);
    app = createApp({
      render: () =>
        h(DataImportWizard, {
          dataImport: wizardFake as unknown as UseDataImport,
          onOpenList,
          onOpenRecord,
        }),
    });
    app.mount(host);
    return { onOpenList, onOpenRecord };
  }

  it("passes the step's events on and shows the status line when not running", () => {
    const { onOpenList, onOpenRecord } = mountWizard({
      logs: [successLog(1, "TD-1")],
    });
    expect(text()).toContain("Successfully imported 2 out of 3 records.");
    button("Go to list").click();
    button("TD-1").click();
    expect(onOpenList).toHaveBeenCalledWith("ToDo");
    expect(onOpenRecord).toHaveBeenCalledWith("ToDo", "TD-1");
  });

  it("hides the status line on the Import step while running", () => {
    mountWizard({
      running: true,
      doc: { status: "In Progress" },
      progress: { current: 1, total: 10 },
    });
    expect(text()).toContain("Importing your data");
    expect(text()).not.toContain("Import Progress");
    expect(text()).not.toContain("Successfully imported");
  });
});
