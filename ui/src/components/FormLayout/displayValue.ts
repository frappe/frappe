/** The string a field shows in a panel row, a read-only form field and a read-only grid cell. */
import { dayjs, formatDuration } from "frappe-ui";
import { NUMBER_FIELDTYPES, formatField, formatRating } from "./formatNumber";
import type { FormatFieldOptions } from "./formatNumber";
import type { FieldMeta } from "../Fields/types";
import { htmlToText } from "../RichText/html";
import { groupIban } from "../Fields/dataOptions";
import { durationUnits } from "../Fields/durationUnits";

export interface DisplayOptions extends FormatFieldOptions {
  /** The record, for a fieldtype that reads a sibling field: Image, Dynamic Link. */
  doc?: Record<string, unknown>;
  /** The record's link titles, keyed `doctype::name`. */
  linkTitles?: Record<string, string>;
  /** dayjs formats for Date, Time and Datetime; ISO when omitted. */
  dateFormat?: string;
  timeFormat?: string;
}

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
  // A `Read Only` field formats as Data with its own `options`, so each Data case applies to it.
  if (field.fieldtype === "Read Only")
    return displayValue(value, { ...field, fieldtype: "Data" }, options);
  const { fieldtype } = field;
  // An Image field holds no value: it shows the attachment its `options` field names.
  if (fieldtype === "Image") return summarize(sibling(field, options), fieldtype);
  if (isSummaryField(fieldtype)) return summarize(value, fieldtype);
  // A Check has no unset state: an absent value is `No`, not a placeholder.
  if (fieldtype === "Check") return value ? "Yes" : "No";
  if (isEmptyValue(value)) return "";
  if (NUMBER_FIELDTYPES.includes(fieldtype))
    return formatField(value, { ...options, fieldtype });
  return formatValue(value, field, options);
}

function formatValue(
  value: unknown,
  field: FieldMeta,
  options: DisplayOptions,
): string {
  const titles = options.linkTitles ?? {};
  const { dateFormat = "YYYY-MM-DD", timeFormat = "HH:mm:ss" } = options;
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
      return formatDuration(Number(value), "short", durationUnits(field));
    case "Date":
      return formatDateTime(String(value), dateFormat);
    case "Time":
      return formatTime(String(value), timeFormat);
    case "Datetime":
      return formatDateTime(String(value), `${dateFormat} ${timeFormat}`);
    case "Password":
      return PASSWORD_MASK;
    case "Select":
    case "Autocomplete":
      return field.choices?.find((one) => one.value === String(value))?.label ?? String(value);
    case "Data":
      return field.options === "IBAN" ? groupIban(String(value)) : String(value);
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

// The server sends `9:15:00`, `14:05:30.000000` or, unpadded, `14:05:5.123456`. A Time can pass 24 hours
// (`25:00:00`), which a clock format would roll over, so it keeps its hours.
function formatTime(value: string, format: string): string {
  const match = /^(\d{1,2}):\d{2}(:\d{1,2})?/.exec(value);
  if (!match) return value;
  if (Number(match[1]) > 23) return match[0];
  return formatDateTime(`2000-01-01 ${match[0]}`, format);
}

// The server sends `2026-10-24` or `2026-10-24 09:15:00.123456`.
function formatDateTime(value: string, format: string): string {
  const date = dayjs(value);
  return date.isValid() ? date.format(format) : value;
}

function firstLine(text: string): string {
  const line = text.split("\n").find((l) => l.trim() !== "");
  return line ? line.trim().replace(/\s+/g, " ") : "Not set";
}
