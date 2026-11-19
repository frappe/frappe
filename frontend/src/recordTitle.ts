// A record's title as the desk draws it: the title field's value as plain text, else the name.

const HTML_FIELDTYPES = ["Text Editor", "HTML Editor"];
const BLOCKS = "p, div, li, br, h1, h2, h3, h4, h5, h6, blockquote, pre, tr";

interface TitleMeta {
	title_field?: string;
	fields?: { fieldname: string; fieldtype: string }[];
}

/** Only an HTML field's value is parsed: a Data value such as `A<B` is text as typed. */
export function recordTitle(
	meta: TitleMeta | null | undefined,
	doc: Record<string, unknown>,
	name: string,
	fieldname = meta?.title_field
): string {
	const value = fieldname ? doc[fieldname] : null;
	if (!value) return name;
	const field = meta?.fields?.find((one) => one.fieldname === fieldname);
	const text = field && HTML_FIELDTYPES.includes(field.fieldtype) ? htmlText(String(value)) : String(value);
	return text.replace(/\s+/g, " ").trim() || name;
}

// A space around each block, so that text on either side does not run into it.
function htmlText(html: string): string {
	const body = new DOMParser().parseFromString(html, "text/html").body;
	for (const block of body.querySelectorAll(BLOCKS)) {
		block.before(" ");
		block.after(" ");
	}
	return body.textContent ?? "";
}
