import { flt, parseLongInt } from "../FormLayout/formatNumber";
import { getFormatDefaults } from "../FormLayout/formatDefaults";

const NUMBER_CONTROL = new Set(["Int", "Long Int", "Float", "Currency", "Percent"]);

/** NumberField's parse: empty is `0`, grouping and decimals follow the site's format. */
export function parseNumberText(fieldtype: string, text: string): number | string {
  const defaults = getFormatDefaults();
  if (fieldtype === "Long Int") return parseLongInt(text, defaults.number_format);
  if (fieldtype === "Int") return Math.trunc(flt(text, { numberFormat: defaults.number_format }));
  return flt(text, {
    numberFormat: defaults.number_format,
    roundingMethod: defaults.rounding_method,
  });
}

export function parsePastedText(fieldtype: string, text: string, options?: string): unknown {
  if (NUMBER_CONTROL.has(fieldtype)) return parseNumberText(fieldtype, text);
  if (fieldtype === "Duration") return flt(text);
  if (fieldtype === "Rating") return ratingValue(text, options);
  if (fieldtype === "Check") return checkValue(text);
  if (fieldtype === "Date") return isoDate(text);
  return text;
}

// RatingField stores a fraction of `options` stars; a pasted star count above 1 is converted.
function ratingValue(text: string, options?: string): number {
  const value = flt(text);
  const stars = Number(options) || 5;
  return Math.min(1, Math.max(0, value > 1 ? value / stars : value));
}

// Spreadsheets copy a boolean as TRUE or FALSE.
function checkValue(text: string): 0 | 1 {
  const value = text.trim().toLowerCase();
  return value === "true" || flt(value) !== 0 ? 1 : 0;
}

/** A date in the site's `date_format` becomes `yyyy-mm-dd`; anything else is kept. */
function isoDate(text: string): string {
  const value = text.trim();
  const parts = value.split(/\D+/);
  const order = (getFormatDefaults().date_format ?? "dd-mm-yyyy").toLowerCase().split(/[^a-z]+/);
  if (/^\d{4}-\d{1,2}-\d{1,2}$/.test(value) || parts.length !== 3 || order.length !== 3) {
    return value;
  }
  const part = (token: string) => parts[order.findIndex((o) => o.startsWith(token))];
  const [year, month, day] = [part("y"), part("m"), part("d")];
  if (!year || year.length !== 4 || !month || !day) return value;
  return `${year}-${month.padStart(2, "0")}-${day.padStart(2, "0")}`;
}
