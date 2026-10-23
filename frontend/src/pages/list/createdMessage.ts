// The toast a list shows after a Create: it names the record by its title, else by its name.
import type { DoctypeMeta } from "@framework/ui/composables/useDoctypeMeta";
import { __ } from "@/i18n";

const HTML_FIELDTYPES = ["Text Editor", "HTML Editor"];
const BLOCKS = "p, div, li, br, h1, h2, h3, h4, h5, h6, blockquote, pre, tr";
const TITLE_LIMIT = 60;

/** The toast's message, as the limited HTML a frappe-ui toast renders. */
export function createdMessage(
	doctype: string,
	meta: DoctypeMeta | null,
	doc: Record<string, unknown>
): string {
	return __("{0} {1} created", [__(doctype), escapeHtml(recordLabel(meta, doc))]);
}

function recordLabel(meta: DoctypeMeta | null, doc: Record<string, unknown>): string {
	const field = meta?.fields?.find((one) => one.fieldname === meta.title_field);
	if (!field || !doc[field.fieldname]) return String(doc.name);
	const value = String(doc[field.fieldname]);
	const text = HTML_FIELDTYPES.includes(field.fieldtype) ? htmlText(value) : value;
	return shorten(text.replace(/\s+/g, " ").trim()) || String(doc.name);
}

// A space after each block, so that paragraphs do not run together.
function htmlText(html: string): string {
	const body = new DOMParser().parseFromString(html, "text/html").body;
	for (const block of body.querySelectorAll(BLOCKS)) block.after(" ");
	return body.textContent ?? "";
}

function shorten(text: string): string {
	const characters = Array.from(text);
	if (characters.length <= TITLE_LIMIT) return text;
	return characters.slice(0, TITLE_LIMIT - 1).join("").trimEnd() + "…";
}

function escapeHtml(text: string): string {
	return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
