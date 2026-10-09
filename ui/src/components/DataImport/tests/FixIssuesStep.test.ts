import { afterEach, describe, expect, it, vi } from "vitest";
import { computed, createApp, defineComponent, h, nextTick, ref } from "vue";
import type { App } from "vue";
import type { DataImportDoc, DataImportPreview } from "../types";
import type { UseDataImport } from "../useDataImport";

// Reka's Select and the Link combobox can't be driven in happy-dom; plain inputs stand in.
vi.mock("frappe-ui", async (importOriginal) => {
  const actual = await importOriginal<typeof import("frappe-ui")>();
  const { defineComponent, h } = await import("vue");
  return {
    ...actual,
    Select: defineComponent({
      props: { modelValue: null, options: Array, disabled: Boolean },
      emits: ["update:modelValue"],
      setup(props, { emit }) {
        return () =>
          h(
            "select",
            {
              "data-test": "select",
              value: props.modelValue,
              disabled: props.disabled,
              onChange: (e: Event) =>
                emit(
                  "update:modelValue",
                  (e.target as HTMLSelectElement).value
                ),
            },
            (props.options as string[]).map((o) => h("option", { value: o }, o))
          );
      },
    }),
  };
});

vi.mock("../../Link", async () => {
  const { defineComponent, h } = await import("vue");
  return {
    Link: defineComponent({
      props: {
        modelValue: null,
        doctype: String,
        disabled: Boolean,
        creatable: Boolean,
        placeholder: String,
      },
      emits: ["update:modelValue", "create"],
      setup(props, { emit }) {
        return () =>
          h("input", {
            "data-test": "link",
            "data-doctype": props.doctype,
            "data-creatable": props.creatable,
            placeholder: props.placeholder,
            value: props.modelValue ?? "",
            disabled: props.disabled,
            onCreate: () => emit("create"),
            onChange: (e: Event) =>
              emit("update:modelValue", (e.target as HTMLInputElement).value),
          });
      },
    }),
  };
});

import FixIssuesStep from "../steps/FixIssuesStep.vue";

let app: App | undefined;

afterEach(() => {
  app?.unmount();
  document.body.innerHTML = "";
  app = undefined;
});

function makeDoc(overrides: Partial<DataImportDoc> = {}): DataImportDoc {
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

function makePreview(warnings: Record<string, any>[] = []): DataImportPreview {
  return {
    columns: [
      { header_title: "Sr. No" },
      { header_title: "Description", df: { label: "Description" } },
      { header_title: "Status", df: { label: "Status" } },
      { header_title: "Extra", skip_import: 1 },
    ],
    data: [
      [2, "Call Bob", "Open", "x"],
      [3, "Email Ann", "Bogus", "y"],
      [4, "Ping Sam", "Bogus", "z"],
    ],
    warnings,
    import_log: [],
    total_number_of_rows: 3,
  };
}

function mount(
  options: {
    doc?: Partial<DataImportDoc>;
    preview?: DataImportPreview | null;
    previewReady?: boolean;
  } = {}
) {
  const doc = ref(makeDoc(options.doc));
  const preview = ref(
    options.preview === undefined ? makePreview() : options.preview
  );
  const previewReady = ref(options.previewReady ?? true);
  const startedHere = ref(false);
  const running = computed(
    () =>
      doc.value.status === "In Progress" ||
      (startedHere.value && doc.value.status === "Pending")
  );
  const dataImport = {
    doc,
    hasImportFile: computed(() => !!doc.value.import_file),
    preview,
    previewReady,
    previewError: ref<string | null>(null),
    running,
    importStarted: computed(
      () => running.value || doc.value.status !== "Pending"
    ),
  } as unknown as UseDataImport;

  const host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp(
    defineComponent({
      setup: () => () => h(FixIssuesStep, { dataImport }),
    })
  );
  app.mount(host);
  return { host, doc, preview, previewReady, startedHere };
}

const skipBox = '[aria-label="Skip"]';
const text = (el: Element) => el.textContent?.replace(/\s+/g, " ").trim() ?? "";
const childTexts = (el: Element) => [...el.children].map(text).join(" ");

function button(host: HTMLElement, label: string) {
  return [...host.querySelectorAll("button")].find((b) => text(b) === label) as
    | HTMLButtonElement
    | undefined;
}

function groupTitles(host: HTMLElement) {
  return [...host.querySelectorAll("section > div:first-child")].map(text);
}

const statusMapping = {
  name: "m1",
  column: 2,
  column_label: "Status",
  source_value: "Bogus",
  no_of_rows: "2",
  row_numbers: "[3, 4]",
  target_value: "",
  fieldname: "status",
  fieldtype: "Select" as const,
  select_options: "Open\nClosed",
};

describe("FixIssuesStep", () => {
  it("groups deduplicated warnings like Desk, rows in number order", () => {
    const { host } = mount({
      doc: {
        template_warnings: JSON.stringify([
          { col: 1, message: "short" },
          { message: "Something is off" },
        ]),
      },
      preview: makePreview([
        {
          row: 3,
          message: "Bad <b>row</b>",
          field: { label: "Status", parent: "ToDo", fieldname: "status" },
        },
        { row: 2, message: "Too few cells" },
        { row: 2, message: "Too few cells" },
        { col: 2, type: "value_mapping", message: "invalid values" },
        { col: 1, message: "a longer column message" },
        { message: "Something is off", type: "info" },
      ]),
    });

    expect(groupTitles(host)).toEqual([
      "Row errors",
      "Mapping warnings",
      "Issues",
    ]);
    expect(host.textContent).not.toContain("Column warnings");
    const rows = [...host.querySelectorAll("[data-row]")];
    expect(rows.map((r) => r.getAttribute("data-row"))).toEqual(["2", "3"]);
    expect(rows[0].querySelectorAll("li")).toHaveLength(1);
    expect(rows[1].querySelector("li")!.innerHTML).toBe(
      "Status: Bad <b>row</b>"
    );
    expect(childTexts(host.querySelector("[data-col='1']")!)).toBe(
      "Column 1 a longer column message"
    );
    expect(host.textContent).toContain("Affected columns: Status.");
    expect(host.textContent).toContain("Something is off");
  });

  it("collapses skipped columns into one line and keeps the ones to act on", () => {
    const { host } = mount({
      preview: makePreview([
        { col: 1, code: "unknown_column", message: "does not match any field" },
        { col: 3, message: "Skipping column Extra", type: "info" },
      ]),
    });
    expect(childTexts(host.querySelector("[data-col='1']")!)).toBe(
      "Column 1 does not match any field"
    );
    expect(host.querySelector("[data-col='3']")).toBeNull();
    expect(host.textContent).not.toContain("Skipping column Extra");
    expect(text(host.querySelector("[data-slot='skipped-columns']")!)).toBe(
      "1 column skipped"
    );
  });

  it("uses the cells of a warned row past the preview, and caps each section's height", async () => {
    const preview = makePreview([{ row: 30, message: "Too many cells" }]);
    preview.warning_rows = [[30, "Late task", "Open", "q"]];
    const { host, doc } = mount({
      doc: { value_mappings: [{ ...statusMapping, target_value: "" }] },
      preview,
    });

    button(host, "Skip Row")!.click();
    await nextTick();
    expect(doc.value.skipped_rows).toEqual([
      { row_number: 30, row_data: JSON.stringify(["Late task", "Open", "q"]) },
    ]);
    const scrollers = [...host.querySelectorAll("[data-slot='scroll']")];
    expect(scrollers.length).toBeGreaterThanOrEqual(2);
    for (const el of scrollers) expect(el.className).toMatch(/max-h-/);
  });

  it("Skip Row adds the row with its cells to skipped_rows; Undo Skip removes it", async () => {
    const { host, doc } = mount({
      preview: makePreview([{ row: 3, message: "Bad" }]),
    });

    button(host, "Skip Row")!.click();
    await nextTick();
    expect(doc.value.skipped_rows).toEqual([
      { row_number: 3, row_data: JSON.stringify(["Email Ann", "Bogus", "y"]) },
    ]);

    button(host, "Undo Skip")!.click();
    await nextTick();
    expect(doc.value.skipped_rows).toEqual([]);
  });

  it("maps a value through a Select, or a Link for Link fields", async () => {
    const { host, doc } = mount({
      doc: {
        value_mappings: [
          statusMapping,
          {
            ...statusMapping,
            name: "m2",
            fieldtype: "Link",
            link_doctype: "User",
            select_options: "",
          },
        ],
      },
      preview: makePreview([
        { col: 2, type: "value_mapping", message: "invalid" },
      ]),
    });

    const select = host.querySelector<HTMLSelectElement>(
      "[data-test='select']"
    )!;
    expect([...select.options].map((o) => o.value)).toEqual(["Open", "Closed"]);
    select.value = "Closed";
    select.dispatchEvent(new Event("change"));
    await nextTick();
    expect(doc.value.value_mappings[0].target_value).toBe("Closed");
    expect(
      host.querySelector("[data-test='link']")!.getAttribute("data-doctype")
    ).toBe("User");
  });

  it("Create on a Link mapping marks the value to be created on import", async () => {
    const orgMapping = {
      ...statusMapping,
      fieldtype: "Link" as const,
      link_doctype: "CRM Organization",
      select_options: "",
      target_value: "",
    };
    const preview = makePreview([
      { col: 2, type: "value_mapping", message: "invalid" },
    ]);
    const link = (host: HTMLElement) =>
      host.querySelector<HTMLInputElement>("[data-test='link']")!;

    const plain = mount({ doc: { value_mappings: [orgMapping] }, preview });
    expect(link(plain.host).dataset.creatable).toBe("false");
    app!.unmount();

    const { host, doc } = mount({
      doc: { value_mappings: [{ ...orgMapping, can_create: 1 }] },
      preview,
    });
    expect(link(host).dataset.creatable).toBe("true");
    link(host).dispatchEvent(new Event("create"));
    await nextTick();
    expect(doc.value.value_mappings[0].create_new).toBe(1);
    expect(link(host).placeholder).toBe("Create Bogus");

    link(host).value = "Bogus Ltd";
    link(host).dispatchEvent(new Event("change"));
    await nextTick();
    expect(doc.value.value_mappings[0]).toMatchObject({
      target_value: "Bogus Ltd",
      create_new: 0,
    });
  });

  it("the Skip checkbox skips every row of a value and locks its mapping", async () => {
    const { host, doc } = mount({
      doc: { value_mappings: [{ ...statusMapping, target_value: "" }] },
    });
    const skip = () => host.querySelector<HTMLElement>(skipBox)!;

    expect(host.textContent).not.toContain("Or skip rows instead");
    skip().click();
    await nextTick();
    expect(doc.value.skipped_rows.map((r) => r.row_number)).toEqual([3, 4]);
    expect(
      host.querySelector<HTMLSelectElement>("[data-test='select']")!.disabled
    ).toBe(true);

    skip().click();
    await nextTick();
    expect(doc.value.skipped_rows).toEqual([]);
  });

  it("Skip all skips every value's rows, and unticks back to none", async () => {
    const { host, doc } = mount({
      doc: {
        value_mappings: [
          { ...statusMapping, target_value: "" },
          {
            ...statusMapping,
            name: "m2",
            source_value: "Other",
            row_numbers: "[2]",
            target_value: "",
          },
        ],
      },
    });
    const all = () =>
      host.querySelector<HTMLInputElement>('[aria-label="Skip all"]')!;
    const rowBoxes = () => host.querySelectorAll<HTMLInputElement>(skipBox);

    rowBoxes()[0].click();
    await nextTick();
    expect(all().indeterminate).toBe(true);

    all().click();
    await nextTick();
    expect(doc.value.skipped_rows.map((r) => r.row_number).sort()).toEqual([
      2, 3, 4,
    ]);
    expect(all().checked).toBe(true);

    all().click();
    await nextTick();
    expect(doc.value.skipped_rows).toEqual([]);
  });

  it("duplicate ID keeps the first row and skips the rest", async () => {
    const { host, doc } = mount({
      preview: makePreview([
        {
          type: "duplicate_id",
          rows: [2, 3, 4],
          message: "Duplicate ID A in rows 2, 3, 4",
        },
      ]),
    });

    button(host, "Keep Row 2, Skip Rest")!.click();
    await nextTick();
    expect(doc.value.skipped_rows.map((r) => r.row_number)).toEqual([3, 4]);
    button(host, "Undo Skip Duplicates")!.click();
    await nextTick();
    expect(doc.value.skipped_rows).toEqual([]);
  });

  it("shows No issues to fix with the file's stats", () => {
    const { host } = mount();

    expect(host.textContent).toContain("No issues to fix");
    expect(host.textContent).toContain(
      "No warnings or mapping issues were found. You can continue to import."
    );
    const stats = [...host.querySelectorAll("[role='listitem']")].map(
      childTexts
    );
    expect(stats).toEqual([
      "3 Rows checked",
      "2 Columns matched",
      "0 Rows skipped",
    ]);
  });

  it("shows the loading skeleton until the preview is ready", async () => {
    const { host, previewReady } = mount({ previewReady: false });
    expect(host.querySelector("[aria-busy='true']")).not.toBeNull();

    previewReady.value = true;
    await nextTick();
    expect(host.querySelector("[aria-busy='true']")).toBeNull();
  });

  it("locks edits while the import runs and hides the panel once it succeeds", async () => {
    const { host, doc, startedHere } = mount({
      doc: { value_mappings: [statusMapping] },
      preview: makePreview([{ row: 3, message: "Bad" }]),
    });

    startedHere.value = true;
    await nextTick();
    expect(button(host, "Skip Row")!.disabled).toBe(true);
    expect(
      host.querySelector<HTMLSelectElement>("[data-test='select']")!.disabled
    ).toBe(true);
    expect(host.querySelector<HTMLInputElement>(skipBox)!.disabled).toBe(true);

    doc.value.status = "Success";
    await nextTick();
    expect(host.textContent).toContain(
      "This import is complete. There are no pending warnings or mapping issues."
    );
  });

  it("after a failed run, rows can still be skipped for a retry (as Desk)", async () => {
    const { host, doc } = mount({
      doc: { status: "Error", value_mappings: [statusMapping] },
      preview: makePreview([{ row: 3, message: "Bad" }]),
    });

    button(host, "Skip Row")!.click();
    await nextTick();
    expect(doc.value.skipped_rows.map((r) => r.row_number)).toEqual([3]);
  });
});
