// The record's picture: which field holds it, whether an upload here would stick, and
// which linked record it comes from when it would not.

export interface ImageSource {
	doctype: string;
	name: string;
}

export interface ImageField {
	fieldname: string;
	/** False when the field is hidden, read-only or fetched from a linked record; `reason` says which. */
	editable: boolean;
	reason: string;
	/** The field's permlevel, for the reader's access to it; a field the meta does not list is 0. */
	permlevel: number;
	source: ImageSource | null;
}

/** The doctype's `image_field`, or nothing when it names none. */
export function imageFieldOf(
	meta: Record<string, any> | null,
	doc: Record<string, any> = {},
	titleOf: (doctype: string, name: string) => string = (_, name) => name
): ImageField | null {
	const fieldname = meta?.image_field;
	if (!fieldname) return null;
	const field = docfield(meta, fieldname);
	const source = fetchSource(field, meta, doc);
	const reason = uneditableReason(field, source, titleOf, linkLabel(field, meta));
	return { fieldname, editable: !reason, reason, source, permlevel: field?.permlevel ?? 0 };
}

// A `fetch_from` without `fetch_if_empty` is rewritten from its source on every save,
// so an upload here would be thrown away.
function uneditableReason(
	field: Record<string, any> | undefined,
	source: ImageSource | null,
	titleOf: (doctype: string, name: string) => string,
	link: string
) {
	if (!field) return "";
	if (field.hidden) return "This image is hidden";
	if (field.read_only) return "This image is read-only";
	if (!field.fetch_from || field.fetch_if_empty) return "";
	if (!source)
		return link
			? `This image is fetched from the record linked in ${link}`
			: "This image is fetched from a linked record";
	return `This image comes from ${titleOf(source.doctype, source.name)}, open it to change`;
}

/** What the form calls the link field the fetch reads through. */
function linkLabel(field: Record<string, any> | undefined, meta: Record<string, any> | null) {
	if (!field?.fetch_from) return "";
	const [linkFieldname] = String(field.fetch_from).split(".");
	const link = docfield(meta, linkFieldname);
	return String(link?.label || linkFieldname || "");
}

/** The record the fetch reads from: whom the link field on this doc points at. */
function fetchSource(
	field: Record<string, any> | undefined,
	meta: Record<string, any> | null,
	doc: Record<string, any>
): ImageSource | null {
	if (!field?.fetch_from) return null;
	const [linkFieldname] = String(field.fetch_from).split(".");
	const link = docfield(meta, linkFieldname);
	const name = String(doc?.[linkFieldname] || "");
	if (!link?.options || !name) return null;
	return { doctype: String(link.options), name };
}

function docfield(meta: Record<string, any> | null, fieldname: string) {
	const fields: any[] = Array.isArray(meta?.fields) ? meta!.fields : [];
	return fields.find((field) => field?.fieldname === fieldname);
}

/** The two letters the tile shows while the record has no picture. */
export function initialsOf(label: string): string {
	return label
		.split(/\s+/)
		.filter(Boolean)
		.slice(0, 2)
		.map((word) => word[0])
		.join("");
}
