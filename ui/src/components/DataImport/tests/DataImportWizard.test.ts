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
  return {
    default: defineComponent({
      props: { showErrors: Boolean },
      setup: (props) => () =>
        h("div", {
          "data-slot": "config",
          "data-show-errors": props.showErrors,
        }),
    }),
  };
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
  const preview = ref(null);
  const previewReady = ref(true);
  const previewLoading = ref(false);
  const previewError = ref<string | null>(null);
  const startedHere = ref(false);
  const blocked = ref(false);
  const startError = ref<string | null>(null);
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
    preview,
    previewReady,
    readyPreview: computed(() => (previewReady.value ? preview.value : null)),
    previewLoading,
    previewError,
    running,
    importStarted: computed(
      () => running.value || doc.value.status !== "Pending"
    ),
    blocked,
    startError,
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
    start: vi.fn(async ({ waitForProgress = false } = {}) => {
      if (!waitForProgress) startedHere.value = true;
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

// Step headings are buttons too; these helpers are about the footer.
const FOOTER_BUTTON = "button:not([data-slot='step'])";

const stepButton = (label: string) =>
  [...host!.querySelectorAll<HTMLButtonElement>("[data-slot='step']")].find(
    (b) => b.textContent?.trim() === label
  )!;

const buttons = () =>
  [...host!.querySelectorAll(FOOTER_BUTTON)].map((b) => b.textContent?.trim());

function click(label: string) {
  const button = [...host!.querySelectorAll(FOOTER_BUTTON)].find(
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
      "Map columns",
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
    expect(stepLabel()).toBe("Map columns");
  });

  it("opens on Preview for a Google Sheet too", () => {
    render(savedDoc({ import_file: null, google_sheets_url: "https://sheet" }));
    expect(stepLabel()).toBe("Map columns");
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
    expect(stepLabel()).toBe("Map columns");
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

  it("Map columns: Back and Next", () => {
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

  it("Next on Config opens Map columns with a skeleton while it saves", async () => {
    const { dataImport, isDirty } = render(savedDoc());
    click("Back");
    await settle();
    let finishSave = () => {};
    dataImport.save.mockImplementationOnce(async () => {
      dataImport.saving.value = true;
      await new Promise<void>((resolve) => (finishSave = resolve));
      dataImport.saving.value = false;
      return dataImport.doc.value;
    });
    dataImport.previewReady.value = false;
    isDirty.value = true;
    await nextTick();
    click("Next");
    await settle();
    // the new step comes in once the old one has faded out
    await new Promise((resolve) => setTimeout(resolve, 300));
    expect(stepLabel()).toBe("Map columns");
    expect(
      host!.querySelector("[role='status'][aria-busy='true']")
    ).not.toBeNull();
    expect(buttons()).toEqual(["Back", "Saving..."]);
    finishSave();
    await settle();
  });

  it("Back during the save stays on Config once the save finishes", async () => {
    const { dataImport, isDirty } = render(savedDoc());
    click("Back");
    await settle();
    let finishSave = () => {};
    dataImport.save.mockImplementationOnce(async () => {
      dataImport.saving.value = true;
      await new Promise<void>((resolve) => (finishSave = resolve));
      dataImport.saving.value = false;
      return dataImport.doc.value;
    });
    isDirty.value = true;
    await nextTick();
    click("Next");
    await settle();
    expect(stepLabel()).toBe("Map columns");
    click("Back");
    await settle();
    expect(stepLabel()).toBe("Config");
    finishSave();
    await settle();
    expect(stepLabel()).toBe("Config");
  });

  it("Next on Config goes back to Config when the save fails", async () => {
    const { dataImport, isDirty } = render(savedDoc());
    click("Back");
    await settle();
    dataImport.save.mockRejectedValueOnce(new Error("nope"));
    isDirty.value = true;
    await nextTick();
    click("Next");
    await settle();
    expect(stepLabel()).toBe("Config");
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
    const solid = [...host!.querySelectorAll(FOOTER_BUTTON)].filter((b) =>
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

  it("Retry shows Retrying... while it saves", async () => {
    const { dataImport, isDirty } = render(savedDoc({ status: "Error" }));
    isDirty.value = true;
    dataImport.save.mockImplementation(() => new Promise(() => {}));
    await nextTick();
    click("Retry");
    await settle();
    expect(buttons()).toContain("Retrying...");
    expect(dataImport.start).not.toHaveBeenCalled();
  });

  it("Retry stays on the result until the import reloads with the new run", async () => {
    const { dataImport } = render(
      savedDoc({ status: "Error", modified: "2026-10-14 10:00:00" })
    );
    click("Retry");
    await settle();
    expect(dataImport.start).toHaveBeenCalledWith({ waitForProgress: true });
    expect(buttons()).toEqual(["Back", "Retrying..."]);

    dataImport.doc.value = {
      ...dataImport.doc.value,
      modified: "2026-10-14 10:05:00",
    };
    await settle();
    expect(buttons()).toEqual(["Back", "Retry"]);
  });

  it("Import becomes Skip all and import while row errors aren't skipped", async () => {
    const { dataImport } = render(
      savedDoc({
        template_warnings: JSON.stringify([
          { row: 4, message: "bad" },
          { row: 3, message: "bad" },
          { row: 4, message: "also bad" },
        ]),
        skipped_rows: [{ row_number: 4, row_data: "[]" }],
      })
    );
    expect(buttons()).toContain("Skip all and import");
    click("Skip all and import");
    await settle();
    expect(
      dataImport.doc.value.skipped_rows.map((row) => row.row_number)
    ).toEqual([4, 3]);
    expect(dataImport.start).toHaveBeenCalledOnce();
  });

  it("Import keeps its label once every row error is skipped", () => {
    render(
      savedDoc({
        template_warnings: JSON.stringify([{ row: 3, message: "bad" }]),
        skipped_rows: [{ row_number: 3, row_data: "[]" }],
      })
    );
    expect(buttons()).toContain("Import");
    expect(buttons()).not.toContain("Skip all and import");
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

  it("Import goes back to Fix issues and shows why when the run can't start", async () => {
    const { dataImport } = render(savedDoc({ template_warnings: '["x"]' }));
    dataImport.start.mockImplementationOnce(async () => {
      dataImport.startError.value =
        "Scheduler is inactive. Cannot import data.";
      return false;
    });
    click("Import");
    await settle();
    expect(stepLabel()).toBe("Fix issues");
    expect(host!.textContent).toContain("Import could not start");
    expect(host!.textContent).toContain(
      "Scheduler is inactive. Cannot import data."
    );
    expect(buttons()).toContain("Import");
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

function configShowsErrors() {
  return (
    document
      .querySelector("[data-slot='config']")
      ?.getAttribute("data-show-errors") === "true"
  );
}

describe("DataImportWizard step headings", () => {
  it("opens an earlier step when its heading is clicked", async () => {
    render(savedDoc());
    expect(stepLabel()).toBe("Map columns");
    stepButton("Config").click();
    await settle();
    expect(stepLabel()).toBe("Config");
  });

  it("can't open a step that isn't ready, or the current one", () => {
    render(savedDoc());
    expect(stepButton("Import").disabled).toBe(true);
    expect(stepButton("Map columns").disabled).toBe(true);
    expect(stepButton("Fix issues").disabled).toBe(false);
  });
});

describe("DataImportWizard locks", () => {
  it("can't leave Config without a file", async () => {
    const { dataImport } = render(savedDoc({ import_file: null }));
    click("Next");
    await settle();
    expect(stepLabel()).toBe("Config");
    expect(dataImport.save).not.toHaveBeenCalled();
    expect(configShowsErrors()).toBe(true);
    expect(document.querySelector("[role='dialog']")).toBeNull();
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
    expect(configShowsErrors()).toBe(true);
    expect(document.querySelector("[role='dialog']")).toBeNull();
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
    expect(labelWhileFetching).toBe("Map columns");
    expect(stepLabel()).toBe("Map columns");
  });

  it("can't reach Fix issues while the preview failed", async () => {
    const { dataImport } = render(savedDoc());
    dataImport.previewReady.value = false;
    dataImport.previewError.value = "Bad file";
    click("Next");
    await settle();
    expect(stepLabel()).toBe("Map columns");
    // shown once, inside the Map columns step, not again in a popup
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
