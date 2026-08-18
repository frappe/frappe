/** Read-state strings for a panel row: one line per field, whatever its fieldtype. */
import { formatField } from "../../components/FormLayout/formatNumber";
import type { FormatFieldOptions } from "../../components/FormLayout/formatNumber";
import type { FieldMeta } from "../../components/Fields/types";

const NUMERIC = ["Int", "Float", "Currency", "Percent"];

// Fieldtypes with no honest 130px row. They keep the row shape but show a
// summary and open in the form instead of a control.
const SUMMARY = [
  "Table",
  "Text Editor",
  "Code",
  "Geolocation",
  "Image",
  "Attach",
];

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
  if (fieldtype === "Text Editor") return firstLine(stripHtml(String(value)));
  if (fieldtype === "Code") return firstLine(String(value));
  return "Set";
}

/**
 * The string a panel row shows when it is not being edited. Returns `''` for an
 * empty value, which is what the row renders its `Add …` placeholder for.
 */
export function displayValue(
  value: unknown,
  field: FieldMeta,
  options: FormatFieldOptions = {},
): string {
  const { fieldtype } = field;
  if (isSummaryField(fieldtype)) return summarize(value, fieldtype);
  // A Check has no unset state: an absent value is `No`, not a placeholder.
  if (fieldtype === "Check") return value ? "Yes" : "No";
  if (isEmptyValue(value)) return "";
  if (NUMERIC.includes(fieldtype))
    return formatField(value, { ...options, fieldtype });
  return String(value);
}

function stripHtml(html: string): string {
  return html.replace(/<[^>]*>/g, " ").replace(/&nbsp;/g, " ");
}

function firstLine(text: string): string {
  const line = text.split("\n").find((l) => l.trim() !== "");
  return line ? line.trim().replace(/\s+/g, " ") : "Not set";
}
