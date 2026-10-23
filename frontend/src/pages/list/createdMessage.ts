// The toast a list shows after a Create: it names the record by its title, else by its name.
import type { DoctypeMeta } from "@framework/ui/composables/useDoctypeMeta";
import { __ } from "@/i18n";

const HTML_FIELDTYPES = ["Text Editor", "HTML Editor"];
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

// Tags become spaces first, so that paragraphs do not run together.
function htmlText(html: string): string {
	const spaced = html.replace(/<[^>]*>/g, " ");
	return new DOMParser().parseFromString(spaced, "text/html").body.textContent ?? "";
}

function shorten(text: string): string {
	if (text.length <= TITLE_LIMIT) return text;
	return text.slice(0, TITLE_LIMIT - 1).trimEnd() + "…";
}

function escapeHtml(text: string): string {
	return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
