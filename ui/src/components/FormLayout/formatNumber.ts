/**
 * Pure, app-agnostic number/currency/percent formatting for `FormLayout`.
 *
 * Ported from Frappe/CRM's `numberFormat.js` but deliberately pure: all
 * site-specific inputs (numberFormat, currency, precision, rounding) arrive as
 * explicit arguments with lib-level defaults rather than reading globals.
 */

/** Locale grouping/decimal table, keyed by Frappe's number-format strings. */
const NUMBER_FORMAT_INFO: Record<
  string,
  { decimalStr: string; groupSep: string }
> = {
  "#,###.##": { decimalStr: ".", groupSep: "," },
  "#.###,##": { decimalStr: ",", groupSep: "." },
  "# ###.##": { decimalStr: ".", groupSep: " " },
  "# ###,##": { decimalStr: ",", groupSep: " " },
  "#'###.##": { decimalStr: ".", groupSep: "'" },
  "#, ###.##": { decimalStr: ".", groupSep: ", " },
  "#,##,###.##": { decimalStr: ".", groupSep: "," },
  "#,###.###": { decimalStr: ".", groupSep: "," },
  "#.###": { decimalStr: "", groupSep: "." },
  "#,###": { decimalStr: "", groupSep: "," },
};

/** Lib default when no site `number_format` is supplied (Frappe's own default). */
export const DEFAULT_NUMBER_FORMAT = "#,###.##";

/** Lib default rounding (Frappe's own default). */
export const DEFAULT_ROUNDING_METHOD = "Banker's Rounding (legacy)";

export interface NumberFormatInfo {
  decimalStr: string;
  groupSep: string;
  /** Decimal-place count derived from the format string. */
  precision: number;
}

export interface FltOptions {
  /** Decimal places to round to. When omitted, no rounding is applied. */
  precision?: number | null;
  numberFormat?: string;
  roundingMethod?: string;
}

export interface FormatNumberOptions {
  numberFormat?: string;
  /** Decimal places. When omitted, derived from `numberFormat`. */
  precision?: number | null;
  roundingMethod?: string;
}

export interface FormatCurrencyOptions {
  numberFormat?: string;
  /** ISO currency code (e.g. `'USD'`). When absent/unresolvable, no symbol. */
  currency?: string | null;
  /** Decimal places. Defaults to 2. */
  precision?: number | null;
  roundingMethod?: string;
}

export interface FormatFieldOptions {
  /** Frappe fieldtype — selects the formatting (Int / Float / Currency / Percent). */
  fieldtype?: string;
  /** Decimal places; when omitted, derived from `numberFormat` (Int forces 0). */
  precision?: number | null;
  /** Resolved currency code for `Currency` fields (caller resolves it). */
  currency?: string | null;
  numberFormat?: string;
  roundingMethod?: string;
}

function replaceAll(s: string, t1: string, t2: string): string {
  return s.split(t1).join(t2);
}

function lstrip(s: string, chars: string[]): string {
  let first = s.charAt(0);
  while (chars.includes(first)) {
    s = s.slice(1);
    first = s.charAt(0);
  }
  return s;
}

function cint(v: unknown, def = 0): number {
  if (v === true) return 1;
  if (v === false) return 0;
  let s = v + "";
  if (s !== "0") s = lstrip(s, ["0"]);
  const n = parseInt(s);
  return isNaN(n) ? def : n;
}

/** Derive separators + precision from a format string. Returns a fresh object (CRM original mutated the shared map). */
export function getNumberFormatInfo(format: string): NumberFormatInfo {
  const base = NUMBER_FORMAT_INFO[format] ?? { decimalStr: ".", groupSep: "," };
  const decimalStr = base.decimalStr;
  // Precision = number of chars after the decimal separator in the format.
  const precision = decimalStr
    ? format.split(decimalStr).slice(1)[0]?.length ?? 0
    : 0;
  return { decimalStr, groupSep: base.groupSep, precision };
}

function stripNumberGroups(v: string, numberFormat: string): string {
  const info = getNumberFormatInfo(numberFormat);

  // Strip group separators.
  if (info.groupSep) {
    const groupRegex = new RegExp(
      info.groupSep === "." ? "\\." : info.groupSep,
      "g"
    );
    v = v.replace(groupRegex, "");
  }

  // Normalise the decimal separator to '.'.
  if (info.decimalStr && info.decimalStr !== ".") {
    v = v.replace(new RegExp(info.decimalStr, "g"), ".");
  }

  return v;
}

/** Parse a value to a Number, tolerating a locale-formatted string. Optionally rounds. Mirrors Frappe's `flt`. */
export function flt(value: unknown, options: FltOptions = {}): number {
  const {
    precision,
    numberFormat = DEFAULT_NUMBER_FORMAT,
    roundingMethod,
  } = options;

  if (value == null || value === "") return 0;

  let v: number;
  if (typeof value === "number") {
    v = value;
  } else {
    let s = value + "";

    // Strip leading currency symbol, but only when the first token isn't numeric
    // (a space can also be a group separator).
    if (s.indexOf(" ") !== -1) {
      const parts = s.split(" ");
      s = isNaN(parseFloat(parts[0]))
        ? parts.slice(parts.length - 1).join(" ")
        : s;
    }

    s = stripNumberGroups(s, numberFormat);
    v = parseFloat(s);
    if (isNaN(v)) v = 0;
  }

  if (precision != null) return roundNumber(v, precision, roundingMethod);
  return v;
}

/** Format a number with locale grouping and fixed decimals (derived from `numberFormat` if omitted). Mirrors `format_number`. */
export function formatNumber(
  value: unknown,
  options: FormatNumberOptions = {}
): string {
  const { numberFormat = DEFAULT_NUMBER_FORMAT, roundingMethod } = options;
  const info = getNumberFormatInfo(numberFormat);

  let decimals = options.precision;
  if (decimals == null) decimals = info.precision;

  let v = flt(value, { precision: decimals, numberFormat, roundingMethod });

  const isNegative = v < 0;
  v = Math.abs(v);

  const fixed = v.toFixed(decimals);
  const part = fixed.split(".");

  // Group the integer part.
  let groupPosition = info.groupSep ? 3 : 0;
  if (groupPosition) {
    const integer = part[0];
    let str = "";
    for (let i = integer.length; i >= 0; i--) {
      let l = replaceAll(str, info.groupSep, "").length;
      if (numberFormat === "#,##,###.##" && str.indexOf(",") !== -1) {
        // Indian grouping: 2 after the first group of 3.
        groupPosition = 2;
        l += 1;
      }
      str += integer.charAt(i);
      if (l && !((l + 1) % groupPosition) && i !== 0) {
        str += info.groupSep;
      }
    }
    part[0] = str.split("").reverse().join("");
  }
  if (part[0] + "" === "") part[0] = "0";

  // Join decimals back with the locale decimal separator.
  part[1] = part[1] && info.decimalStr ? info.decimalStr + part[1] : "";

  return (isNegative ? "-" : "") + part[0] + part[1];
}

/** Format a number with a currency-symbol prefix (`Intl` lookup); falls back to a plain number. Mirrors `format_currency`. */
export function formatCurrency(
  value: unknown,
  options: FormatCurrencyOptions = {}
): string {
  const {
    numberFormat = DEFAULT_NUMBER_FORMAT,
    currency,
    roundingMethod,
  } = options;
  const precision = options.precision ?? 2;

  const number = formatNumber(value, {
    numberFormat,
    precision,
    roundingMethod,
  });

  if (currency) {
    const symbol = getCurrencySymbol(currency);
    if (symbol) return symbol + " " + number;
  }
  return number;
}

/**
 * Format a value the way a Frappe numeric field renders, by `fieldtype` (Int / Currency /
 * Percent / Float). Returns `''` for empty. Currency code is caller-resolved to keep this
 * free of doc/Vue coupling.
 */
export function formatField(
  value: unknown,
  options: FormatFieldOptions = {}
): string {
  if (value == null || value === "") return "";
  const { fieldtype, precision, currency, numberFormat, roundingMethod } =
    options;
  switch (fieldtype) {
    case "Int":
      // Frappe's Int formatter returns a plain integer, NO grouping — don't route
      // through `formatNumber` (which would group it, e.g. `1,234,567`).
      return String(cint(value));
    case "Currency":
      return formatCurrency(value, {
        numberFormat,
        currency,
        precision,
        roundingMethod,
      });
    case "Percent":
      return (
        formatNumber(value, { numberFormat, precision, roundingMethod }) + "%"
      );
    default: // Float and any other numeric fieldtype
      return formatNumber(value, { numberFormat, precision, roundingMethod });
  }
}

/** Look up a currency's symbol via `Intl`. Returns `null` for an invalid code. */
export function getCurrencySymbol(currencyCode: string): string | null {
  try {
    const formatter = new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currencyCode,
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    });
    const part = formatter.formatToParts(1).find((p) => p.type === "currency");
    return part ? part.value : null;
  } catch {
    return null;
  }
}

function roundNumber(
  num: number,
  precision: number,
  roundingMethod?: string
): number {
  const method = roundingMethod || DEFAULT_ROUNDING_METHOD;
  const isNegative = num < 0;

  if (method === "Banker's Rounding (legacy)") {
    const d = cint(precision);
    const m = Math.pow(10, d);
    const n = +(d ? Math.abs(num) * m : Math.abs(num)).toFixed(8);
    const i = Math.floor(n);
    const f = n - i;
    let r = !precision && f === 0.5 ? (i % 2 === 0 ? i : i + 1) : Math.round(n);
    r = d ? r / m : r;
    return isNegative ? -r : r;
  } else if (method === "Banker's Rounding") {
    if (num === 0) return 0;
    const p = cint(precision);
    const multiplier = Math.pow(10, p);
    let n = Math.abs(num) * multiplier;
    const floorNum = Math.floor(n);
    const decimalPart = n - floorNum;
    const epsilon = 2.0 ** (Math.log2(Math.abs(n)) - 52.0);
    n =
      Math.abs(decimalPart - 0.5) < epsilon
        ? floorNum % 2 === 0
          ? floorNum
          : floorNum + 1
        : Math.round(n);
    n = n / multiplier;
    return isNegative ? -n : n;
  } else if (method === "Commercial Rounding") {
    if (num === 0) return 0;
    const digits = cint(precision);
    const multiplier = Math.pow(10, digits);
    let n = num * multiplier;
    let epsilon = 2.0 ** (Math.log2(Math.abs(n)) - 52.0);
    if (isNegative) epsilon = -1 * epsilon;
    n = Math.round(n + epsilon);
    return n / multiplier;
  }
  // Unknown method — fall back to legacy Banker's Rounding rather than crashing
  // the NumberField's display computed (which would leave every numeric field blank).
  console.warn(
    `[FormLayout] Unknown rounding method "${method}", falling back to Banker's Rounding (legacy)`
  );
  return roundNumber(num, precision, DEFAULT_ROUNDING_METHOD);
}
