// Fetch from: the Link fields a field fetches through, the fields of the linked DocType it can
// fetch, and the name of the field "Fetch a field…" adds.
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import { __ } from "@/i18n";
import { fieldnameFromLabel, LAYOUT_BREAKS, validFieldname } from "./fieldRules";

/** The field of the linked DocType a fetch copies. */
export type FetchSource = Pick<RawMetaField, "fieldname" | "label" | "fieldtype" | "options">;

/** `fetch_from` split at its first dot; `null` when it is not `<link>.<field>`. */
export interface FetchPath {
	link: string;
	source: string;
}

// `no_value_fields` and Dynamic Link (its options name a field of the other DocType), as the save refuses.
const UNFETCHABLE = [
	...LAYOUT_BREAKS,
	...["Attachment Gallery", "HTML", "Button", "Heading", "Image", "Fold", "Vue Component"],
	...["Table", "Table MultiSelect", "Dynamic Link"],
];

export function linkFields(fields: readonly RawMetaField[], except?: string): RawMetaField[] {
	return fields.filter((field) => field.fieldtype === "Link" && field.options && field.fieldname !== except);
}

export function fetchSources(fields: readonly RawMetaField[]): RawMetaField[] {
	return fields.filter(fetchable);
}

/** A field that holds a value, so it can fetch one or be fetched. */
export function fetchable(field: Pick<RawMetaField, "fieldtype">): boolean {
	return !UNFETCHABLE.includes(field.fieldtype);
}

export function fetchFromText(path: FetchPath): string {
	return `${path.link}.${path.source}`;
}

export function parseFetchFrom(value: string | null | undefined): FetchPath | null {
	const [link, ...rest] = (value ?? "").split(".");
	const source = rest.join(".");
	return link && source ? { link, source } : null;
}

/** The source's label as a fieldname, `_1`, `_2`… added while another field has it. */
export function fetchedFieldname(source: FetchSource, taken: readonly string[], prefix = ""): string {
	const spelled = fieldnameFromLabel(source.label ?? "");
	const name = validFieldname(spelled) ? spelled : source.fieldname;
	const base = name.startsWith(prefix) ? name : `${prefix}${name}`;
	let fieldname = base;
	for (let n = 1; taken.includes(fieldname); n++) fieldname = `${base}_${n}`;
	return fieldname;
}

const FETCHED_SHOWN = 3;

/** "Fetched now: A, B, C and 4 more." for the fields that copy from the Link; "" when none does. */
export function fetchedLine(fields: readonly RawMetaField[], link: string): string {
	const names = fields
		.filter((field) => parseFetchFrom(field.fetch_from)?.link === link)
		.map((field) => field.label || field.fieldname);
	if (!names.length) return "";
	const shown = names.slice(0, FETCHED_SHOWN).join(", ");
	const rest = names.length - FETCHED_SHOWN;
	return __("Fetched now: {0}.", [rest > 0 ? __("{0} and {1} more", [shown, rest]) : shown]);
}
