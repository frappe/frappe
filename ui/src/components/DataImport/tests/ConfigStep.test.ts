import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { computed, createApp, h, nextTick, ref } from "vue";
import type { App } from "vue";
import type { DataImportDoc, DocType } from "../types";
import type { UseDataImport } from "../useDataImport";

const mocks = vi.hoisted(() => ({
  call: vi.fn(),
  upload: vi.fn(),
  warning: vi.fn(),
  error: vi.fn(),
  uploadState: { uploading: false, progress: 0 },
}));

vi.mock("frappe-ui", async (importOriginal) => {
  const actual = await importOriginal<typeof import("frappe-ui")>();
  const { reactive } = await import("vue");
  mocks.uploadState = reactive({ uploading: false, progress: 0 });
  return {
    ...actual,
    call: mocks.call,
    toast: Object.assign(vi.fn(), {
      warning: mocks.warning,
      error: mocks.error,
    }),
    useFileUpload: () => ({
      upload: mocks.upload,
      state: mocks.uploadState,
    }),
  };
});

vi.mock("../../Link", async () => {
  const { defineComponent, h } = await import("vue");
  return {
    Link: defineComponent({
      props: ["modelValue", "disabled"],
      setup: (props) => () =>
        h("input", {
          "data-fieldname": "reference_doctype",
          value: props.modelValue,
          disabled: props.disabled,
        }),
    }),
  };
});

import ConfigStep from "../steps/ConfigStep.vue";
import TemplateModal from "../steps/TemplateModal.vue";

let app: App | undefined;
let host: HTMLElement | undefined;

beforeEach(() => {
  mocks.call.mockReset();
  mocks.call.mockResolvedValue(0);
  mocks.upload.mockReset();
  Object.assign(mocks.uploadState, { uploading: false, progress: 0 });
  mocks.warning.mockReset();
  mocks.error.mockReset();
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
    delimiter_options: ",;\\\\t|",
    value_mappings: [],
    skipped_rows: [],
    ...overrides,
  };
}

/** The composable's state as plain refs; `dirty` compares with the last save, as the real one does. */
function fakeDataImport(initial: DataImportDoc, meta: DocType[] | null = null) {
  const doc = ref(initial);
  const saved = ref(JSON.stringify(initial));
  const isNew = computed(() => !doc.value.name);
  const saving = ref(false);
  return {
    doc,
    isNew,
    saving,
    dirty: computed(
      () => isNew.value || JSON.stringify(doc.value) !== saved.value
    ),
    preview: ref(null),
    providerSchema: ref(null),
    doctypeMeta: ref(meta),
    save: vi.fn(async () => {
      saving.value = true;
      doc.value = { ...doc.value, name: doc.value.name ?? "DI-NEW" };
      saved.value = JSON.stringify(doc.value);
      saving.value = false;
      return doc.value;
    }),
    refreshGoogleSheet: vi.fn(async () => null),
  };
}

function render(
  initial: DataImportDoc,
  meta: DocType[] | null = null,
  listeners: Record<string, unknown> = {}
) {
  const dataImport = fakeDataImport(initial, meta);
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({
    render: () =>
      h(ConfigStep, {
        dataImport: dataImport as unknown as UseDataImport,
        ...listeners,
      }),
  });
  app.mount(host);
  return dataImport;
}

async function settle() {
  for (let i = 0; i < 10; i++) {
    await Promise.resolve();
    await nextTick();
  }
}

const field = (fieldname: string) =>
  host!.querySelector<HTMLInputElement>(
    `[data-fieldname="${fieldname}"] input, input[data-fieldname="${fieldname}"]`
  );

const buttonLabels = () =>
  [...document.body.querySelectorAll("button")].map((b) =>
    b.textContent?.trim()
  );

function clickButton(label: string) {
  const button = [...document.body.querySelectorAll("button")].find(
    (b) => b.textContent?.trim() === label
  );
  if (!button) throw new Error(`no "${label}" button`);
  button.click();
}

const tabs = () =>
  [...host!.querySelectorAll('[role="tab"]')].map((tab) =>
    tab.textContent?.trim()
  );

describe("ConfigStep settings", () => {
  it("edits the doc from the checkboxes", async () => {
    const { doc } = render(savedDoc({ name: undefined }));
    field("mute_emails")!.click();
    await nextTick();
    expect(doc.value.mute_emails).toBe(0);

    field("custom_delimiters")!.click();
    await nextTick();
    expect(doc.value.custom_delimiters).toBe(1);
    expect(field("delimiter_options")).not.toBeNull();
  });

  it("keeps the set-only-once settings read-only once saved", () => {
    render(savedDoc());
    expect(field("reference_doctype")!.disabled).toBe(true);
    expect(field("mute_emails")!.disabled).toBe(true);
  });

  it("hides the CSV options until a CSV file or sheet is chosen", () => {
    render(savedDoc({ import_file: "/private/files/todo.xlsx" }));
    expect(field("custom_delimiters")).toBeNull();
    expect(field("use_csv_sniffer")).toBeNull();
  });

  it("offers Submit After Import only for submittable doctypes", async () => {
    const { doctypeMeta } = render(savedDoc({ name: undefined }), [
      { name: "ToDo", fields: [], is_submittable: 0 },
    ]);
    expect(field("submit_after_import")).toBeNull();
    doctypeMeta.value = [{ name: "ToDo", fields: [], is_submittable: 1 }];
    await nextTick();
    expect(field("submit_after_import")).not.toBeNull();
  });

  it("shows the pending imports banner for a new import", async () => {
    mocks.call.mockResolvedValue(2);
    render(savedDoc({ name: undefined, import_file: null }));
    await settle();
    expect(mocks.call).toHaveBeenCalledWith("frappe.client.get_count", {
      doctype: "Data Import",
      filters: {
        reference_doctype: "ToDo",
        status: "Pending",
        import_file: ["is", "set"],
      },
    });
    expect(host!.textContent).toContain(
      "You have 2 pending ToDo imports with files attached."
    );
    expect(buttonLabels()).toContain("Review pending imports");
  });

  it("Review pending imports asks the app to show that doctype's imports", async () => {
    mocks.call.mockResolvedValue(1);
    const onOpenImports = vi.fn();
    render(savedDoc({ name: undefined, import_file: null }), null, {
      onOpenImports,
    });
    await settle();
    [...host!.querySelectorAll("button")]
      .find((b) => b.textContent?.trim() === "Review pending imports")!
      .click();
    await settle();
    expect(onOpenImports).toHaveBeenCalledWith("ToDo");
  });
});

describe("ConfigStep upload", () => {
  function pickFile(file: File) {
    const input = host!.querySelector<HTMLInputElement>('input[type="file"]')!;
    Object.defineProperty(input, "files", {
      value: [file],
      configurable: true,
    });
    input.dispatchEvent(new Event("change"));
  }

  it("sets import_file and saves after an upload", async () => {
    mocks.upload.mockResolvedValue({ file_url: "/private/files/new.csv" });
    const dataImport = render(savedDoc({ name: undefined, import_file: null }));
    pickFile(new File(["a,b"], "new.csv"));
    await settle();
    expect(mocks.upload).toHaveBeenCalledOnce();
    expect(dataImport.doc.value.import_file).toBe("/private/files/new.csv");
    expect(dataImport.save).toHaveBeenCalledOnce();
    expect(
      host!.querySelector('[data-slot="file-card"]')?.textContent
    ).toContain("new.csv");
  });

  it("shows the file name and progress while uploading", async () => {
    mocks.upload.mockReturnValue(new Promise(() => {}));
    render(savedDoc({ name: undefined, import_file: null }));
    pickFile(new File(["a,b"], "new.csv"));
    Object.assign(mocks.uploadState, { uploading: true, progress: 40 });
    await settle();
    const progress = host!.querySelector('[data-slot="upload-progress"]')!;
    expect(progress.textContent).toContain("new.csv");
    expect(progress.textContent).toContain("Uploading 40%");
  });

  it("skips a file of another type", async () => {
    render(savedDoc({ name: undefined, import_file: null }));
    pickFile(new File(["x"], "notes.pdf"));
    await settle();
    expect(mocks.upload).not.toHaveBeenCalled();
    expect(mocks.warning).toHaveBeenCalledWith(
      'File "notes.pdf" was skipped because of invalid file type'
    );
  });

  it("shows the source tabs only while no source is chosen", async () => {
    render(savedDoc({ name: undefined, import_file: null }));
    expect(tabs()).toEqual(["File upload", "Google Sheet"]);
    app!.unmount();
    host!.remove();

    render(savedDoc());
    expect(tabs()).toEqual([]);
    expect(field("google_sheets_url")).toBeNull();
    expect(host!.querySelector('[data-slot="file-card"]')).not.toBeNull();
    expect(buttonLabels()).toContain("Clear");
  });

  it("keeps the source tab on the first save, resets it for another import", async () => {
    const dataImport = render(savedDoc({ name: undefined, import_file: null }));
    const sheetTab = [
      ...host!.querySelectorAll<HTMLElement>('[role="tab"]'),
    ][1];
    sheetTab.dispatchEvent(
      new MouseEvent("mousedown", { bubbles: true, button: 0 })
    );
    sheetTab.click();
    await settle();
    expect(field("google_sheets_url")).not.toBeNull();

    await dataImport.save();
    await settle();
    expect(field("google_sheets_url")).not.toBeNull();

    dataImport.doc.value = savedDoc({ name: "DI-2", import_file: null });
    await settle();
    expect(field("google_sheets_url")).toBeNull();
  });

  it("locks the file and CSV options after a finished import", () => {
    render(savedDoc({ status: "Success", custom_delimiters: 1 }));
    expect(host!.querySelector('[data-slot="file-card"]')).not.toBeNull();
    expect(buttonLabels()).not.toContain("Clear");
    expect(field("custom_delimiters")!.disabled).toBe(true);
    expect(field("delimiter_options")!.disabled).toBe(true);
    expect(field("use_csv_sniffer")!.disabled).toBe(true);
  });

  it("shows a saved Google Sheet as a link bar with Refresh", async () => {
    const url = "https://docs.google.com/spreadsheets/d/abc/edit";
    const dataImport = render(
      savedDoc({ import_file: null, google_sheets_url: url })
    );
    expect(tabs()).toEqual([]);
    expect(
      host!.querySelector('[data-slot="sheet-card"]')?.textContent
    ).toContain(url);
    clickButton("Refresh Google Sheet");
    expect(dataImport.refreshGoogleSheet).toHaveBeenCalledOnce();

    clickButton("Clear");
    await settle();
    expect(dataImport.doc.value.google_sheets_url).toBe("");
    expect(dataImport.save).toHaveBeenCalledOnce();
  });
});

describe("TemplateModal", () => {
  const meta: DocType[] = [
    {
      name: "Contact",
      autoname: "hash",
      fields: [
        {
          fieldname: "first_name",
          label: "First Name",
          fieldtype: "Data",
          reqd: 1,
        },
        {
          fieldname: "email_id",
          label: "Email",
          fieldtype: "Data",
          reqd: 0,
          in_import_template: 1,
        },
        { fieldname: "company", label: "Company", fieldtype: "Data", reqd: 0 },
        {
          fieldname: "sb",
          label: "Section",
          fieldtype: "Section Break",
          reqd: 0,
        },
        {
          fieldname: "phone_nos",
          label: "Phones",
          fieldtype: "Table",
          options: "Contact Phone",
          reqd: 0,
          in_import_template: 1,
        },
        {
          fieldname: "links",
          label: "Links",
          fieldtype: "Table",
          options: "Dynamic Link",
          reqd: 0,
        },
      ],
    },
    {
      name: "Contact Phone",
      fields: [
        { fieldname: "phone", label: "Phone", fieldtype: "Data", reqd: 1 },
        {
          fieldname: "is_primary",
          label: "Primary",
          fieldtype: "Check",
          reqd: 0,
        },
      ],
    },
    {
      name: "Dynamic Link",
      fields: [
        {
          fieldname: "link_name",
          label: "Link Name",
          fieldtype: "Data",
          reqd: 1,
        },
      ],
    },
  ];

  function checked(group: string) {
    return [
      ...document.body.querySelectorAll<HTMLInputElement>(
        `[data-group="${group}"] input[data-option]`
      ),
    ]
      .filter((input) => input.checked)
      .map((input) => input.dataset.option);
  }

  it("selects mandatory and in_import_template fields when it opens", async () => {
    host = document.createElement("div");
    document.body.appendChild(host);
    app = createApp({
      render: () =>
        h(TemplateModal, {
          open: true,
          doctype: "Contact",
          importType: "Insert New Records",
          providerSchema: null,
          doctypeMeta: meta,
        }),
    });
    app.mount(host);
    await settle();

    expect(checked("Contact")).toEqual(["first_name", "email_id"]);
    expect(checked("phone_nos")).toEqual(["phone"]);
    expect(checked("links")).toEqual([]);
    expect(document.body.textContent).toContain("Phones (Contact Phone)");
    expect(document.body.textContent).not.toContain("Section");
  });

  it("keeps ID ticked on Unselect All for an update import", async () => {
    host = document.createElement("div");
    document.body.appendChild(host);
    app = createApp({
      render: () =>
        h(TemplateModal, {
          open: true,
          doctype: "Contact",
          importType: "Update Existing Records",
          providerSchema: null,
          doctypeMeta: meta,
        }),
    });
    app.mount(host);
    await settle();
    clickButton("Select All");
    await settle();
    clickButton("Unselect All");
    await settle();

    expect(checked("Contact")).toEqual(["name"]);
    expect(checked("phone_nos")).toEqual(["name"]);
  });
});
