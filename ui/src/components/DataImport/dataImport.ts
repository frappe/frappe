import { t } from "./translate";
import type { DataImportStatus, DocField, DocType } from "./types";

export const getBadgeColor = (status: DataImportStatus) => {
  const colorMap = {
    Pending: "amber",
    "In Progress": "amber",
    Success: "green",
    "Partial Success": "amber",
    Error: "red",
    "Timed Out": "amber",
  } as const;
  return colorMap[status as DataImportStatus] || "gray";
};

/** Desk's is_import_complete: the records are in, so the import can't be edited. */
export const isImportComplete = (status: DataImportStatus) =>
  status === "Success" || status === "Partial Success";

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
