// The value a control commits for text typed or pasted into it.
import { flt, parseLongInt } from "../FormLayout/formatNumber";
import { getFormatDefaults } from "../FormLayout/formatDefaults";

const NUMBER_CONTROL = new Set(["Int", "Long Int", "Float", "Currency", "Percent"]);
// Stored as numbers, though their own controls take no typed text.
const DECIMALS = new Set(["Rating", "Duration"]);

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

/** A cell of a pasted block, as the column's control would commit it. */
export function parsePastedText(fieldtype: string, text: string): unknown {
  if (NUMBER_CONTROL.has(fieldtype)) return parseNumberText(fieldtype, text);
  if (DECIMALS.has(fieldtype)) return flt(text);
  if (fieldtype === "Check") return checkValue(text);
  if (fieldtype === "Date") return isoDate(text);
  return text;
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
