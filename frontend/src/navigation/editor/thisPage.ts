// "Add this page": the page under the dialog as a row to add. A saved view offers nothing: a
// View row is not addable yet.

import type { Addresses } from "@/addresses";
import type { EditorRow } from "./draft";

export type ThisPage = { type: string; label: string; fields: Omit<EditorRow, "key"> };

type Where = { name?: unknown; params: Record<string, unknown>; meta?: { title?: unknown } };

export function thisPage(where: Where, addresses: Addresses, app: string | null): ThisPage | null {
	const name = String(where.name ?? "");
	if (name.startsWith(`page:${app}:`)) return pageRow(name, app!, where.meta?.title);

	const slug = where.params.doctype;
	const doctype = typeof slug === "string" ? addresses.doctypeOf(slug) : null;
	if (!doctype) return null;

	if (name === "list" || name === "standard-list") return doctypeRow(doctype);
	if (name === "record" || name === "standard-record") return recordRow(doctype, where.params.name);
	return null;
}

function doctypeRow(doctype: string): ThisPage {
	return {
		type: "DocType",
		label: doctype,
		fields: { item_type: "DocType", link_doctype: "DocType", link_to: doctype },
	};
}

function recordRow(doctype: string, name: unknown): ThisPage | null {
	if (typeof name !== "string" || !name) return null;
	return {
		type: "Record",
		label: name,
		fields: { item_type: "Record", link_doctype: doctype, link_to: name },
	};
}

function pageRow(routeName: string, app: string, title: unknown): ThisPage {
	const slug = routeName.slice(`page:${app}:`.length);
	return {
		type: "Page",
		label: typeof title === "string" && title ? title : slug,
		fields: { item_type: "Page", link_doctype: "Page", link_to: slug },
	};
}
