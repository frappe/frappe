import type { FieldMeta } from "./types";

/** Where a Data value leads when nobody edits it: an Email's mail link or a URL's web page. */
export interface DataHref {
  kind: "mail" | "web";
  href: string;
}

// v1 leaves these countries' IBANs ungrouped.
const UNGROUPED_IBAN = ["BI", "SV", "EG", "LY"];

/** The `options` of a Data field, which a `Read Only` field shares; `undefined` for any other type. */
export function dataOption(field: FieldMeta): string | undefined {
  if (field.fieldtype !== "Data" && field.fieldtype !== "Read Only") return undefined;
  return field.options || undefined;
}

/** The input's `type` and `inputmode` for a Data option; the browser checks nothing. */
export function dataInputAttrs(option: string | undefined): {
  type: "text" | "tel";
  inputmode?: "email" | "url";
} {
  if (option === "Email") return { type: "text", inputmode: "email" };
  if (option === "URL") return { type: "text", inputmode: "url" };
  if (option === "Phone") return { type: "tel" };
  return { type: "text" };
}

export function dataHref(field: FieldMeta, value: unknown): DataHref | null {
  const option = dataOption(field);
  if (typeof value !== "string" || !value.trim()) return null;
  if (option === "Email") return mailHref(value);
  if (option === "URL") {
    const href = webHref(value);
    return href ? { kind: "web", href } : null;
  }
  return null;
}

export function groupIban(value: string): string {
  if (!value || UNGROUPED_IBAN.some((country) => value.startsWith(country))) return value;
  return stripIban(value).replace(/(.{4})(?=.)/g, "$1 ");
}

export function stripIban(value: string): string {
  return value.replace(/\s/g, "");
}

function mailHref(value: string): DataHref | null {
  const addresses = value
    .split(/[,;]/)
    .map((address) => address.trim())
    .filter(Boolean)
    .map((address) => encodeURIComponent(address).replace(/%40/g, "@"));
  return addresses.length ? { kind: "mail", href: `mailto:${addresses.join(",")}` } : null;
}

// Only `http` and `https`: a `javascript:` or `data:` value must never become a link.
function webHref(value: string): string | null {
  try {
    const url = new URL(value.trim());
    return url.protocol === "http:" || url.protocol === "https:" ? url.href : null;
  } catch {
    return null;
  }
}
