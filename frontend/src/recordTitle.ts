// A record's title as the desk draws it: the title field's value as plain text, else the name.

const BLOCKS = "p, div, li, br, h1, h2, h3, h4, h5, h6, blockquote, pre, tr";

/** The same text the server's `RecordTitles` gives, for a value that may hold HTML. */
export function recordTitle(
	meta: { title_field?: string } | null | undefined,
	doc: Record<string, unknown>,
	name: string
): string {
	const value = meta?.title_field ? doc[meta.title_field] : null;
	return (value ? plainText(String(value)) : "") || name;
}

// A space around each block, so that text on either side does not run into it.
function plainText(html: string): string {
	const body = new DOMParser().parseFromString(html, "text/html").body;
	for (const block of body.querySelectorAll(BLOCKS)) {
		block.before(" ");
		block.after(" ");
	}
	return (body.textContent ?? "").replace(/\s+/g, " ").trim();
}
