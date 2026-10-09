import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { computed, createApp, h, nextTick, ref } from "vue";
import type { App } from "vue";
import type { DataImportDoc } from "../types";
import type { UseDataImport } from "../useDataImport";

const toasts = vi.hoisted(() => ({
  error: vi.fn(),
  warning: vi.fn(),
  plain: vi.fn(),
}));

vi.mock("frappe-ui", async (importOriginal) => {
  const actual = await importOriginal<typeof import("frappe-ui")>();
  return {
    ...actual,
    toast: Object.assign(toasts.plain, {
      error: toasts.error,
      warning: toasts.warning,
    }),
  };
});

// The shell is under test here; ConfigStep has its own tests and loads data on mount.
vi.mock("../steps/ConfigStep.vue", async () => {
  const { defineComponent, h } = await import("vue");
  return { default: defineComponent({ setup: () => () => h("div") }) };
});

import DataImportWizard from "../DataImportWizard.vue";

let app: App | undefined;
let host: HTMLElement | undefined;

beforeEach(() => {
  toasts.error.mockReset();
  toasts.warning.mockReset();
  toasts.plain.mockReset();
});

afterEach(() => {
  app?.unmount();
  host?.remove();
  document.body.innerHTML = "";
  app = undefined;
  host = undefined;
});

function savedDoc(overrides: Partial<DataImportDoc> = {}): DataImportDoc {
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
    template_warnings: null,
    value_mappings: [],
    skipped_rows: [],
    ...overrides,
  };
}

/** The composable's state as plain refs, with its actions as spies. */
function fakeDataImport(initial: DataImportDoc) {
  const doc = ref(initial);
  const loading = ref(false);
  const saving = ref(false);
  const isDirty = ref(false);
  const previewReady = ref(true);
  const previewLoading = ref(false);
  const previewError = ref<string | null>(null);
  const startedHere = ref(false);
  const blocked = ref(false);
  const isNew = computed(() => !doc.value.name);
  const running = computed(
    () =>
      doc.value.status === "In Progress" ||
      (startedHere.value && doc.value.status === "Pending")
  );

  const fake = {
    doc,
    isNew,
    dirty: computed(() => isNew.value || isDirty.value),
    loading,
    saving,
    hasImportFile: computed(
      () => !!(doc.value.import_file || doc.value.google_sheets_url)
    ),
    preview: ref(null),
    previewReady,
    previewLoading,
    previewError,
    running,
    importStarted: computed(
      () => running.value || doc.value.status !== "Pending"
    ),
    blocked,
    progress: ref(null),
    importStatus: ref(null),
    logFilter: ref("all"),
    logs: ref([]),
    save: vi.fn(async () => {
      saving.value = true;
      await Promise.resolve();
      doc.value = { ...doc.value, name: doc.value.name ?? "DI-NEW" };
      saving.value = false;
      isDirty.value = false;
      return doc.value;
    }),
    fetchPreview: vi.fn(async () => null),
    start: vi.fn(async () => {
      startedHere.value = true;
      return true;
    }),
    stop: vi.fn(async () => ({ status: "success", message: "" })),
  };
  return { fake, isDirty };
}

function render(
  initial: DataImportDoc,
  listeners: Record<string, unknown> = {}
) {
  const { fake, isDirty } = fakeDataImport(initial);
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({
    render: () =>
      h(DataImportWizard, {
        dataImport: fake as unknown as UseDataImport,
        ...listeners,
      }),
  });
  app.mount(host);
  return { dataImport: fake, isDirty };
}

async function settle() {
  for (let i = 0; i < 10; i++) {
    await Promise.resolve();
    await nextTick();
  }
}

const stepLabel = () =>
  host!.querySelector('[aria-current="step"]')?.textContent?.trim();

const buttons = () =>
  [...host!.querySelectorAll("button")].map((b) => b.textContent?.trim());

function click(label: string) {
  const button = [...host!.querySelectorAll("button")].find(
    (b) => b.textContent?.trim() === label
  );
  if (!button) throw new Error(`no "${label}" button`);
  button.click();
}

describe("DataImportWizard step header", () => {
  it("names every step and fills the bars up to the current one", () => {
    render(savedDoc({ skipped_rows: [{ row_number: 2, row_data: "[]" }] }));
    const steps = [...host!.querySelectorAll('[data-slot="steps"] li')];
    expect(steps.map((li) => li.textContent?.trim())).toEqual([
      "Config",
      "Preview",
      "Fix issues",
      "Import",
    ]);
    expect(
      steps.map((li) => !!li.querySelector(".bg-surface-gray-10"))
    ).toEqual([true, true, true, false]);
    expect(steps[2].getAttribute("aria-current")).toBe("step");
  });
});

describe("DataImportWizard landing step", () => {
  it("opens a new import on Config", () => {
    render(savedDoc({ name: undefined, import_file: null }));
    expect(stepLabel()).toBe("Config");
  });

  it("opens a saved import with no file on Config", () => {
    render(savedDoc({ import_file: null }));
    expect(stepLabel()).toBe("Config");
  });

  it("opens an import with a file on Preview", () => {
    render(savedDoc());
    expect(stepLabel()).toBe("Preview");
  });

  it("opens on Preview for a Google Sheet too", () => {
    render(savedDoc({ import_file: null, google_sheets_url: "https://sheet" }));
    expect(stepLabel()).toBe("Preview");
  });

  it.each([
    ["skipped rows", { skipped_rows: [{ row_number: 2, row_data: "[]" }] }],
    [
      "value mappings",
      {
        value_mappings: [
          {
            source_value: "x",
            column: 1,
            fieldname: "status",
            fieldtype: "Select" as const,
          },
        ],
      },
    ],
    ["template warnings", { template_warnings: '[{"message":"bad"}]' }],
  ])("opens on Fix issues when there are %s", (_, overrides) => {
    render(savedDoc(overrides));
    expect(stepLabel()).toBe("Fix issues");
  });

  it("ignores template warnings that are not valid JSON", () => {
    render(savedDoc({ template_warnings: "{oops" }));
    expect(stepLabel()).toBe("Preview");
  });

  it.each(["In Progress", "Success", "Partial Success", "Error", "Timed Out"])(
    "opens a %s import on Import",
    (status) => {
      render(savedDoc({ status: status as DataImportDoc["status"] }));
      expect(stepLabel()).toBe("Import");
    }
  );

  it("lands again when another import is loaded", async () => {
    const { dataImport } = render(savedDoc({ import_file: null }));
    dataImport.loading.value = true;
    dataImport.doc.value = savedDoc({ name: "DI-2", status: "Success" });
    dataImport.loading.value = false;
    await settle();
    expect(stepLabel()).toBe("Import");
  });

  it("stays on the step when the first save names the import", async () => {
    const { dataImport } = render(
      savedDoc({ name: undefined, import_file: null })
    );
    dataImport.doc.value.import_file = "/private/files/todo.csv";
    await dataImport.save();
    await settle();
    expect(dataImport.doc.value.name).toBe("DI-NEW");
    expect(stepLabel()).toBe("Config");
  });
});

describe("DataImportWizard footer", () => {
  it("Config: Next only", () => {
    render(savedDoc({ import_file: null }));
    expect(buttons()).toEqual(["Next"]);
  });

  it("Preview: Back and Next", () => {
    render(savedDoc());
    expect(buttons()).toEqual(["Back", "Next"]);
  });

  it("Fix issues before the import: Import, edited or not", async () => {
    const { isDirty } = render(savedDoc({ template_warnings: '["x"]' }));
    expect(buttons()).toEqual(["Back", "Import"]);
    isDirty.value = true;
    await nextTick();
    expect(buttons()).toEqual(["Back", "Import"]);
  });

  it("Fix issues after the import started: Back and Next", async () => {
    render(savedDoc({ status: "Success" }));
    click("Back");
    await settle();
    expect(stepLabel()).toBe("Fix issues");
    expect(buttons()).toEqual(["Back", "Next"]);
  });

  it("shows Loading preview... while the preview loads", async () => {
    const { dataImport } = render(savedDoc());
    dataImport.previewLoading.value = true;
    await nextTick();
    expect(buttons()).toEqual(["Back", "Loading preview..."]);
  });

  it("Import while running: Cancel Import", () => {
    render(savedDoc({ status: "In Progress" }));
    expect(buttons()).toEqual(["Back", "Cancel Import"]);
  });

  it.each(["Error", "Partial Success", "Timed Out"])(
    "Import after %s: Retry",
    (status) => {
      render(savedDoc({ status: status as DataImportDoc["status"] }));
      expect(buttons()).toEqual(["Back", "Retry"]);
    }
  );

  it("after a failure, Start new import leads and Retry follows", () => {
    const onNewImport = vi.fn();
    render(savedDoc({ status: "Error" }), { onNewImport });
    expect(buttons()).toEqual(["Back", "Retry", "Start new import"]);
    click("Start new import");
    expect(onNewImport).toHaveBeenCalledWith("ToDo");
  });

  it("after a timeout, Retry leads", () => {
    render(savedDoc({ status: "Timed Out" }), { onNewImport: vi.fn() });
    const solid = [...host!.querySelectorAll("button")].filter((b) =>
      b.classList.contains("bg-surface-gray-10")
    );
    expect(solid.map((b) => b.textContent?.trim())).toEqual(["Retry"]);
  });

  it("Import after Success: Start new import, no Retry", () => {
    render(savedDoc({ status: "Success" }), { onNewImport: vi.fn() });
    expect(buttons()).toEqual(["Back", "Start new import"]);
  });

  it("Import after Success without a new import handler: Back only", () => {
    render(savedDoc({ status: "Success" }));
    expect(buttons()).toEqual(["Back"]);
  });

  it("Import starts the run and opens the Import step", async () => {
    const { dataImport } = render(savedDoc({ template_warnings: '["x"]' }));
    click("Import");
    await settle();
    expect(dataImport.start).toHaveBeenCalledOnce();
    expect(stepLabel()).toBe("Import");
    expect(buttons()).toEqual(["Back", "Cancel Import"]);
  });

  it("Retry starts the run again", async () => {
    const { dataImport } = render(savedDoc({ status: "Error" }));
    click("Retry");
    await settle();
    expect(dataImport.start).toHaveBeenCalledOnce();
  });

  it("Import saves unsaved fixes first, then starts the run", async () => {
    const { dataImport, isDirty } = render(
      savedDoc({ template_warnings: '["x"]' })
    );
    isDirty.value = true;
    await nextTick();
    click("Import");
    await settle();
    expect(dataImport.save).toHaveBeenCalledOnce();
    expect(dataImport.start).toHaveBeenCalledOnce();
    expect(
      dataImport.save.mock.invocationCallOrder[0] <
        dataImport.start.mock.invocationCallOrder[0]
    ).toBe(true);
    expect(stepLabel()).toBe("Import");
  });

  it("Import stays on Fix issues when the save fails", async () => {
    const { dataImport, isDirty } = render(
      savedDoc({ template_warnings: '["x"]' })
    );
    dataImport.save.mockRejectedValueOnce(new Error("nope"));
    isDirty.value = true;
    await nextTick();
    click("Import");
    await settle();
    expect(dataImport.start).not.toHaveBeenCalled();
    expect(stepLabel()).toBe("Fix issues");
  });

  it("Cancel Import asks first, then stops", async () => {
    const { dataImport } = render(savedDoc({ status: "In Progress" }));
    click("Cancel Import");
    await settle();
    expect(document.body.textContent).toContain(
      "This will terminate the job immediately and might be dangerous, are you sure?"
    );
    expect(dataImport.stop).not.toHaveBeenCalled();
    const yes = [...document.body.querySelectorAll("button")].find(
      (b) => b.textContent?.trim() === "Yes"
    )!;
    yes.click();
    await settle();
    expect(dataImport.stop).toHaveBeenCalledOnce();
    expect(toasts.plain).toHaveBeenCalledWith("Job Stopped Successfully");
  });
});

describe("DataImportWizard locks", () => {
  it("can't leave Config without a file", async () => {
    const { dataImport } = render(savedDoc({ import_file: null }));
    click("Next");
    await settle();
    expect(stepLabel()).toBe("Config");
    expect(dataImport.save).not.toHaveBeenCalled();
    expect(document.body.textContent).toContain(
      "Please attach an import file or provide a Google Sheets URL."
    );
  });

  it("doesn't save a new import that has no file", async () => {
    const { dataImport } = render(
      savedDoc({ name: undefined, import_file: null })
    );
    click("Next");
    await settle();
    expect(dataImport.save).not.toHaveBeenCalled();
    expect(stepLabel()).toBe("Config");
  });

  it("can't leave Config without a document type", async () => {
    render(savedDoc({ reference_doctype: "" }));
    click("Back");
    await settle();
    click("Next");
    await settle();
    expect(stepLabel()).toBe("Config");
    expect(document.body.textContent).toContain(
      "Please select Document Type and Import Type."
    );
  });

  it("opens Preview first, then waits for the preview", async () => {
    const { dataImport } = render(savedDoc());
    click("Back");
    await settle();
    dataImport.previewReady.value = false;
    let labelWhileFetching: string | undefined;
    dataImport.fetchPreview.mockImplementationOnce(async () => {
      await nextTick();
      labelWhileFetching = stepLabel();
      dataImport.previewReady.value = true;
      return null;
    });
    click("Next");
    await settle();
    expect(dataImport.fetchPreview).toHaveBeenCalledOnce();
    expect(labelWhileFetching).toBe("Preview");
    expect(stepLabel()).toBe("Preview");
  });

  it("can't reach Fix issues while the preview failed", async () => {
    const { dataImport } = render(savedDoc());
    dataImport.previewReady.value = false;
    dataImport.previewError.value = "Bad file";
    click("Next");
    await settle();
    expect(stepLabel()).toBe("Preview");
    // shown once, inside the Preview step, not again in a popup
    expect(document.body.textContent!.split("Bad file").length - 1).toBe(1);
  });

  it("moves from Preview to Fix issues once the preview is ready", async () => {
    render(savedDoc());
    click("Next");
    await settle();
    expect(stepLabel()).toBe("Fix issues");
  });

  it("has no way to the Import step before the import starts", async () => {
    render(savedDoc({ template_warnings: '["x"]' }));
    expect(buttons()).not.toContain("Next");
  });

  it("reaches Import from Fix issues after the import started", async () => {
    render(savedDoc({ status: "Partial Success" }));
    click("Back");
    await settle();
    click("Next");
    await settle();
    expect(stepLabel()).toBe("Import");
  });
});

describe("DataImportWizard blocked import", () => {
  it("says why and opens Fix issues", async () => {
    const { dataImport } = render(savedDoc({ status: "In Progress" }));
    expect(stepLabel()).toBe("Import");
    dataImport.doc.value = { ...dataImport.doc.value, status: "Pending" };
    dataImport.blocked.value = true;
    await settle();
    expect(stepLabel()).toBe("Fix issues");
    expect(toasts.error).toHaveBeenCalledWith(
      "Import could not start. Please resolve the errors in the import file."
    );
  });
});
