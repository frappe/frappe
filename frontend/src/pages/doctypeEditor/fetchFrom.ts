// Fetch from: the Link fields a field fetches through, the fields of the linked DocType it can
// fetch, and the name of the field "Fetch a field…" adds.
import { shallowRef } from "vue";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
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

/** The Link field whose "Fetch a field…" the canvas menu asked the field panel to open. */
export const fetchAsked = shallowRef<string | null>(null);

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
