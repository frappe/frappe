import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, ref } from "vue";
import type { App } from "vue";
import type { DataImportDoc, DataImportPreview, DocType } from "../types";
import type { UseDataImport } from "../useDataImport";

// Popovers don't open in happy-dom, so the pickers render their choices inline.
vi.mock("frappe-ui", async (importOriginal) => {
  const actual = await importOriginal<typeof import("frappe-ui")>();
  const Combobox = defineComponent({
    props: ["modelValue", "options", "disabled"],
    emits: ["update:modelValue"],
    setup(props, { emit }) {
      return () =>
        h(
          "div",
          {
            "data-combobox": "",
            "data-value": props.modelValue,
            "data-disabled": props.disabled ? "" : undefined,
          },
          props.options.map((option: { label: string; value: string }) =>
            h(
              "button",
              {
                "data-option": option.value,
                disabled: props.disabled,
                onClick: () => emit("update:modelValue", option.value),
              },
              option.label
            )
          )
        );
    },
  });
  const Dropdown = defineComponent({
    props: ["options"],
    setup(props, { slots }) {
      return () =>
        h("div", [
          slots.default?.(),
          ...props.options[0].options.map(
            (item: { label: string; onClick: () => void }) =>
              h(
                "button",
                { "data-format": item.label, onClick: item.onClick },
                item.label
              )
          ),
        ]);
    },
  });
  return { ...actual, Combobox, Dropdown };
});

import PreviewStep from "../steps/PreviewStep.vue";

let app: App | undefined;
let host: HTMLElement | undefined;

afterEach(() => {
  app?.unmount();
  host?.remove();
  document.body.innerHTML = "";
  app = undefined;
  host = undefined;
});

const LONG_TEXT = "A very long description ".repeat(20).trim();

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
    template_options: null,
    value_mappings: [],
    skipped_rows: [],
    ...overrides,
  };
}

function makePreview(
  overrides: Partial<DataImportPreview> = {}
): DataImportPreview {
  return {
    columns: [
      { header_title: "Sr. No", skip_import: true },
      {
        header_title: "Description",
        df: {
          fieldname: "description",
          label: "Description",
          fieldtype: "Text",
        },
      },
      {
        header_title: "Due",
        df: { fieldname: "date", label: "Due Date", fieldtype: "Date" },
        date_format: "%d/%m/%Y",
      },
      { header_title: "Extra", skip_import: true },
    ],
    data: [
      [2, LONG_TEXT, "01/02/2024", "x"],
      [3, "Short", "02/02/2024", "y"],
    ],
    warnings: [],
    import_log: [{ row_indexes: "[2]", success: 1 }],
    total_number_of_rows: 25,
    max_rows_exceeded: true,
    max_rows_in_preview: 10,
    ...overrides,
  };
}

const META: DocType[] = [
  {
    name: "ToDo",
    fields: [
      {
        label: "Description",
        fieldname: "description",
        fieldtype: "Text",
        reqd: 1,
      },
      { label: "Due Date", fieldname: "date", fieldtype: "Date", reqd: 0 },
      {
        label: "Details",
        fieldname: "sb",
        fieldtype: "Section Break",
        reqd: 0,
      },
      {
        label: "Items",
        fieldname: "items",
        fieldtype: "Table",
        reqd: 0,
        options: "ToDo Item",
      },
    ],
  },
  {
    name: "ToDo Item",
    fields: [{ label: "Note", fieldname: "note", fieldtype: "Data", reqd: 0 }],
  },
];

function fakeDataImport({
  doc = makeDoc(),
  preview = makePreview() as DataImportPreview | null,
  previewLoading = false,
  previewError = null as string | null,
} = {}) {
  const fake = {
    doc: ref(doc),
    saving: ref(false),
    preview: ref(preview),
    previewLoading: ref(previewLoading),
    previewError: ref(previewError),
    providerSchema: ref(null),
    doctypeMeta: ref(META),
    save: vi.fn(async () => fake.doc.value),
  };
  return fake;
}

async function mount(fake: ReturnType<typeof fakeDataImport>) {
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({
    render: () =>
      h(PreviewStep, { dataImport: fake as unknown as UseDataImport }),
  });
  app.mount(host);
  await nextTick();
  return host;
}

const headerPicker = (el: HTMLElement, column: number) =>
  el
    .querySelectorAll<HTMLElement>("thead th")
    [column].querySelector<HTMLElement>("[data-combobox]")!;
const DATE_PILL = '[data-slot="date-format"]';
const bodyRows = (el: HTMLElement) => el.querySelectorAll("tbody tr");

describe("PreviewStep", () => {
  it("shows the mapping picker in each column header with Don't Import and the fields", async () => {
    const el = await mount(fakeDataImport());
    expect(el.querySelector("thead th")!.textContent).toBe("Sr");
    const picker = headerPicker(el, 1);
    expect(picker.dataset.value).toBe("description");
    const values = [...picker.querySelectorAll("button")].map(
      (b) => b.dataset.option
    );
    expect(values).toEqual([
      "Don't Import",
      "name",
      "description",
      "date",
      "items.name",
      "items.note",
    ]);
    expect(
      picker.querySelector('[data-option="items.note"]')!.textContent
    ).toBe("Note (Items)");
    expect(headerPicker(el, 3).dataset.value).toBe("Don't Import");
  });

  it("writes column_to_field_map and saves when a column is remapped", async () => {
    const fake = fakeDataImport();
    const el = await mount(fake);
    headerPicker(el, 3)
      .querySelector<HTMLElement>('[data-option="description"]')!
      .click();
    await nextTick();
    expect(JSON.parse(fake.doc.value.template_options!)).toEqual({
      column_to_field_map: { "2": "description" },
    });
    expect(fake.save).toHaveBeenCalledTimes(1);
  });

  it("greys a column set to Don't Import and lists it under the table", async () => {
    const fake = fakeDataImport();
    const el = await mount(fake);
    const cell = (row: number, col: number) =>
      bodyRows(el)[row].querySelectorAll("td")[col];
    expect(cell(2, 3).className).toContain("bg-surface-gray-2");
    expect(cell(2, 1).className).not.toContain("bg-surface-gray-2");
    expect(el.textContent).toContain("Not imported:");

    headerPicker(el, 1)
      .querySelector<HTMLElement>('[data-option="Don\'t Import"]')!
      .click();
    await nextTick();
    expect(cell(2, 1).className).toContain("bg-surface-gray-2");
    expect(cell(2, 1).className).toContain("text-ink-gray-4");
  });

  it("shows the file's header row first and greys rows already imported", async () => {
    const el = await mount(fakeDataImport());
    const rows = bodyRows(el);
    expect(rows).toHaveLength(3);
    const headerCells = [...rows[0].querySelectorAll("td")].map((td) =>
      td.textContent?.trim()
    );
    expect(headerCells[0]).toBe("1");
    expect(headerCells[1]).toBe("Description");
    expect(headerCells[3]).toBe("Extra");
    expect(rows[1].hasAttribute("data-imported")).toBe(true);
    expect(rows[2].hasAttribute("data-imported")).toBe(false);
  });

  it("keeps cells on one line with the full value kept for hover", async () => {
    const el = await mount(fakeDataImport());
    const cell = bodyRows(el)[1].querySelectorAll("td")[1];
    expect(cell.className).toContain("max-w-0");
    const text = cell.querySelector("span")!;
    expect(text.className).toContain("truncate");
    expect(text.textContent).toBe(LONG_TEXT);
    expect(el.querySelector("table")!.className).toContain("table-fixed");
    expect(el.querySelectorAll("col")).toHaveLength(4);
  });

  it("writes column_to_date_format_map from the date format menu", async () => {
    const fake = fakeDataImport();
    const el = await mount(fake);
    const pill = el.querySelector<HTMLButtonElement>(DATE_PILL)!;
    expect(pill.title).toBe("dd/mm/yyyy");
    el.querySelector<HTMLElement>('[data-format="yyyy-mm-dd"]')!.click();
    await nextTick();
    expect(JSON.parse(fake.doc.value.template_options!)).toEqual({
      column_to_date_format_map: { "1": "%Y-%m-%d" },
    });
    expect(fake.save).toHaveBeenCalledTimes(1);
    expect(pill.title).toBe("yyyy-mm-dd");
  });

  it("offers a detected format that is not a common one", async () => {
    const preview = makePreview();
    preview.columns[2].date_format = "%d %B %Y";
    const el = await mount(fakeDataImport({ preview }));
    expect(
      el.querySelector('[data-format="dd Month yyyy (detected)"]')
    ).not.toBeNull();
  });

  it("says how many rows are shown", async () => {
    const el = await mount(fakeDataImport());
    expect(
      el.querySelector("[data-testid=row-count]")!.textContent!.trim()
    ).toBe("Showing first 10 rows of 25");
  });

  it("says all rows are shown when the file is small", async () => {
    const preview = makePreview({
      total_number_of_rows: 2,
      max_rows_exceeded: false,
    });
    const el = await mount(fakeDataImport({ preview }));
    expect(
      el.querySelector("[data-testid=row-count]")!.textContent!.trim()
    ).toBe("Showing all 2 rows");
  });

  it("disables mapping and date format once the import succeeded", async () => {
    const fake = fakeDataImport({ doc: makeDoc({ status: "Success" }) });
    const el = await mount(fake);
    expect(headerPicker(el, 1).hasAttribute("data-disabled")).toBe(true);
    expect(el.querySelector<HTMLButtonElement>(DATE_PILL)!.disabled).toBe(true);
    expect(el.textContent).not.toContain("Map each file column to a field.");
  });

  it("shows a loading skeleton until the preview arrives", async () => {
    const fake = fakeDataImport({ preview: null, previewLoading: true });
    const el = await mount(fake);
    expect(
      el.querySelector('[role="status"][aria-busy="true"]')
    ).not.toBeNull();
    expect(el.querySelector("table")).toBeNull();

    fake.preview.value = makePreview();
    fake.previewLoading.value = false;
    await nextTick();
    expect(el.querySelector('[role="status"]')).toBeNull();
    expect(el.querySelector("table")).not.toBeNull();
  });

  it("shows the preview error", async () => {
    const fake = fakeDataImport({ preview: null, previewError: "Bad file" });
    const el = await mount(fake);
    expect(el.textContent).toContain("Could not load import file");
    expect(el.textContent).toContain("Bad file");
  });
});
