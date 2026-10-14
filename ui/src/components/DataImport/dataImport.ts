import { t } from "./translate";
import type {
  DataImportDoc,
  DataImportPreview,
  DataImportStatus,
  DataImportWarning,
  DocField,
  DocType,
} from "./types";

/** Desk's is_import_complete: the records are in, so the import can't be edited. */
export const isImportComplete = (status: DataImportStatus) =>
  status === "Success" || status === "Partial Success";

/** Rows the file check warned about, saved or from the latest preview, in order. */
export function errorRowNumbers(
  doc: DataImportDoc,
  preview: DataImportPreview | null | undefined
): number[] {
  const saved = parseJson<DataImportWarning[]>(doc.template_warnings, []);
  const rows = new Set<number>();
  for (const warning of saved.concat(preview?.warnings ?? [])) {
    if (warning.row) rows.add(Number(warning.row));
  }
  return [...rows].sort((a, b) => a - b);
}

/** A row's cells, from the first rows shown or from the warned rows past them. */
export function previewRowCells(
  preview: DataImportPreview | null | undefined,
  row: number
): unknown[] | undefined {
  const { data = [], warning_rows = [] } = preview ?? {};
  return [...data, ...warning_rows].find((cells) => Number(cells[0]) === row);
}

/** Adds the rows to `skipped_rows`, keeping their cells for the skipped rows export. */
export function skipRows(
  doc: DataImportDoc,
  preview: DataImportPreview | null | undefined,
  rows: number[]
) {
  const skipped = new Set(
    doc.skipped_rows.map((row) => Number(row.row_number))
  );
  for (const row of rows) {
    if (skipped.has(row)) continue;
    const cells = previewRowCells(preview, row);
    doc.skipped_rows.push({
      row_number: row,
      row_data: JSON.stringify(cells ? cells.slice(1) : []),
    });
  }
}

/** Like Desk's cint, but keeps `fallback` for anything that isn't a number. */
export const cint = (value: unknown, fallback = 0) =>
  Number.isFinite(Number(value)) ? Math.trunc(Number(value)) : fallback;

/** The server stores JSON in text fields, which can be empty or malformed. */
export function parseJson<T>(value: string | null | undefined, fallback: T): T {
  if (!value) return fallback;
  try {
    return JSON.parse(value) ?? fallback;
  } catch {
    return fallback;
  }
}

export function escapeHtml(text: string) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** Desk's open_url_post: a hidden form POST, so the browser downloads the file the server sends back. */
export function postDownload(url: string, params: Record<string, unknown>) {
  const form = document.createElement("form");
  form.action = url;
  form.method = "POST";
  form.style.display = "none";
  const values = { ...params };
  const token = (globalThis as { csrf_token?: string }).csrf_token;
  if (token && token !== "{{ csrf_token }}") values.csrf_token = token;
  for (const [name, value] of Object.entries(values)) {
    const field = document.createElement("textarea");
    field.name = name;
    field.value = typeof value === "string" ? value : JSON.stringify(value);
    form.appendChild(field);
  }
  document.body.appendChild(form);
  form.submit();
  form.remove();
}

const NO_VALUE_FIELDTYPES = [
  "Section Break",
  "Column Break",
  "Tab Break",
  "Attachment Gallery",
  "HTML",
  "Table",
  "Table MultiSelect",
  "Button",
  "Image",
  "Fold",
  "Heading",
];
const TABLE_FIELDTYPES = ["Table", "Table MultiSelect"];

export type PickerField = Partial<DocField> & { fieldname: string };

/** Desk's get_table_fields: the doctype's child tables, without virtual ones. */
export const tableFields = (meta: DocType | null | undefined) =>
  (meta?.fields ?? []).filter(
    (df) => TABLE_FIELDTYPES.includes(df.fieldtype) && !df.is_virtual
  );

/** Desk's get_columns_for_picker for one doctype: an ID, then every field that holds a value. */
export const pickerColumns = (
  meta: DocType | null | undefined
): PickerField[] => [
  { label: t("ID"), fieldname: "name", fieldtype: "Data", reqd: 1 },
  ...(meta?.fields ?? []).filter(
    (df) =>
      !NO_VALUE_FIELDTYPES.includes(df.fieldtype) &&
      !["lft", "rgt"].includes(df.fieldname) &&
      !df.is_virtual
  ),
];
