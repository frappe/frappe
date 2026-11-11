// The toast a list shows after a Create: it names the record by its title, else by its name.
import type { DoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { __ } from "@/i18n";
import { recordTitle } from "@/recordTitle";

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
	return shorten(recordTitle(meta, doc, String(doc.name)));
}

function shorten(text: string): string {
	const characters = Array.from(text);
	if (characters.length <= TITLE_LIMIT) return text;
	return characters.slice(0, TITLE_LIMIT - 1).join("").trimEnd() + "…";
}

function escapeHtml(text: string): string {
	return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
