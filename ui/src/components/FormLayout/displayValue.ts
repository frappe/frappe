/** The string a field shows in a panel row, a read-only form field and a read-only grid cell. */
import { formatDuration } from "frappe-ui";
import { formatField, formatRating } from "./formatNumber";
import type { FormatFieldOptions } from "./formatNumber";
import type { FieldMeta } from "../Fields/types";
import { htmlToText } from "../RichText/html";

export interface DisplayOptions extends FormatFieldOptions {
  /** The record, for a fieldtype that reads a sibling field: Image, Dynamic Link. */
  doc?: Record<string, unknown>;
  /** The record's link titles, keyed `doctype::name`. */
  linkTitles?: Record<string, string>;
}

const NUMERIC = ["Int", "Long Int", "Float", "Currency", "Percent"];

const CODE = ["Code", "JSON", "Markdown Editor", "HTML Editor"];

// Fieldtypes with no honest 130px row. They keep the row shape but show a
// summary and open in the form instead of a control.
const SUMMARY = [
  "Table",
  "Text Editor",
  ...CODE,
  "Geolocation",
  "Image",
  "Attach",
  "Attach Image",
];

// The same for every value, so the row does not give away a password's length.
const PASSWORD_MASK = "••••••••";

/** Whether the fieldtype shows a summary and a trailing `↗` instead of a control. */
export function isSummaryField(fieldtype: string): boolean {
  return SUMMARY.includes(fieldtype);
}

/** Whether a value reads as unset — `null`, blank, or an empty child table. */
export function isEmptyValue(value: unknown): boolean {
  if (Array.isArray(value)) return value.length === 0;
  return value == null || value === "";
}

/** One line standing in for a value the row cannot render: a count, a first line, or `Set`. */
export function summarize(value: unknown, fieldtype: string): string {
  if (isEmptyValue(value)) return "Not set";
  if (Array.isArray(value))
    return `${value.length} ${value.length === 1 ? "item" : "items"}`;
  if (fieldtype === "Text Editor") return firstLine(htmlToText(String(value)));
  if (CODE.includes(fieldtype)) return firstLine(String(value));
  return "Set";
}

/** A field's display string; `''` when empty, so each caller draws its own placeholder. */
export function displayValue(
  value: unknown,
  field: FieldMeta,
  options: DisplayOptions = {},
): string {
  if (field.fieldtype === "Read Only")
    return displayValue(value, { ...field, fieldtype: "Data" }, options);
  const { fieldtype } = field;
  // An Image field holds no value: it shows the attachment its `options` field names.
  if (fieldtype === "Image") return summarize(sibling(field, options), fieldtype);
  if (isSummaryField(fieldtype)) return summarize(value, fieldtype);
  // A Check has no unset state: an absent value is `No`, not a placeholder.
  if (fieldtype === "Check") return value ? "Yes" : "No";
  if (isEmptyValue(value)) return "";
  if (NUMERIC.includes(fieldtype))
    return formatField(value, { ...options, fieldtype });
  return formatValue(value, field, options);
}

function formatValue(
  value: unknown,
  field: FieldMeta,
  options: DisplayOptions,
): string {
  const titles = options.linkTitles ?? {};
  switch (field.fieldtype) {
    case "Link":
      return linkTitle(field.options, value, titles);
    case "Dynamic Link":
      return linkTitle(sibling(field, options), value, titles);
    case "Table MultiSelect":
      return multiSelectTitles(value, field, titles);
    case "Rating":
      return formatRating(Number(value), field.options);
    case "Duration":
      return formatDuration(Number(value));
    case "Time":
      return formatTime(String(value));
    case "Datetime":
      return formatDatetime(String(value));
    case "Password":
      return PASSWORD_MASK;
    default:
      return String(value);
  }
}

/** The linked titles of a Table MultiSelect's rows, comma-joined, as the form's chips show them. */
function multiSelectTitles(
  rows: unknown,
  field: FieldMeta,
  titles: Record<string, string>,
): string {
  const link = field.childFields?.find((f) => f.fieldtype === "Link");
  if (!link || !Array.isArray(rows)) return summarize(rows, field.fieldtype);
  return rows
    .map((row) => row?.[link.fieldname])
    .filter((name) => !isEmptyValue(name))
    .map((name) => linkTitle(link.options, name, titles))
    .join(", ");
}

function linkTitle(
  doctype: unknown,
  name: unknown,
  titles: Record<string, string>,
): string {
  return titles[`${doctype}::${name}`] || String(name);
}

function sibling(field: FieldMeta, options: DisplayOptions): unknown {
  return field.options ? options.doc?.[field.options] : undefined;
}

// The server sends `9:15:00`; the form's TimePicker shows `09:15`.
function formatTime(value: string): string {
  const match = /^(\d{1,2}):(\d{2})/.exec(value);
  return match ? `${match[1].padStart(2, "0")}:${match[2]}` : value;
}

// The server sends `2026-10-24 09:15:00.123456`; the form's DateTimePicker shows
// `2026-10-24 09:15:00`.
function formatDatetime(value: string): string {
  const match = /^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})/.exec(value);
  return match ? `${match[1]} ${match[2]}` : value;
}

function firstLine(text: string): string {
  const line = text.split("\n").find((l) => l.trim() !== "");
  return line ? line.trim().replace(/\s+/g, " ") : "Not set";
}
