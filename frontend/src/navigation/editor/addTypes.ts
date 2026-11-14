// The add-row picker's step list: one entry per type a person can add. #47402 (Act) and #47418
// (View) each add an entry here and a branch in `EditorRowForm.vue`; nothing else changes.

import { __ } from "@/i18n";
import type { EditorRow } from "./draft";
import { RAIL } from "./draft";

export type AddType = {
	type: string;
	label: string;
	icon: string;
	/** A section holds rows, so the rail (which is flat) has none. */
	rail: boolean;
};

export function addTypes(container: string): AddType[] {
	const all: AddType[] = [
		{ type: "DocType", label: __("DocType"), icon: "lucide-table", rail: true },
		{ type: "Record", label: __("Record"), icon: "lucide-file-text", rail: true },
		{ type: "Page", label: __("Page"), icon: "lucide-layout-dashboard", rail: true },
		{ type: "Link", label: __("Link"), icon: "lucide-link", rail: true },
		{ type: "Section", label: __("Section"), icon: "lucide-heading", rail: false },
	];
	return all.filter((entry) => container !== RAIL || entry.rail);
}

export type AddValues = {
	doctype: string;
	name: string;
	page: string;
	url: string;
	label: string;
	collapsible: boolean;
	keepClosed: boolean;
};

/** A form's starting values: empty, or the fields "Add this page" read off the page. */
export function startValues(fields: Partial<EditorRow> = {}): AddValues {
	const doctype = fields.item_type === "DocType" ? fields.link_to : fields.link_doctype;
	return {
		doctype: doctype && fields.item_type !== "Page" ? doctype : "",
		name: fields.item_type === "Record" ? (fields.link_to ?? "") : "",
		page: fields.item_type === "Page" ? (fields.link_to ?? "") : "",
		url: fields.url ?? "",
		label: fields.item_type === "DocType" ? "" : (fields.label ?? ""),
		collapsible: false,
		keepClosed: false,
	};
}

/** What a form needs filled before "Add row"; the refusal is shown under the field. */
export function missing(type: string, values: AddValues): { field: keyof AddValues; message: string } | null {
	if (type === "DocType" && !values.doctype) return { field: "doctype", message: __("Pick a DocType.") };
	if (type === "Record" && !values.doctype) return { field: "doctype", message: __("Pick a DocType.") };
	if (type === "Record" && !values.name) return { field: "name", message: __("Pick a record.") };
	if (type === "Page" && !values.page) return { field: "page", message: __("Pick a page.") };
	if (type === "Link" && !values.url.trim()) return { field: "url", message: __("Write a link.") };
	if (type === "Section" && !values.label.trim()) return { field: "label", message: __("Give the section a label.") };
	return null;
}

/** The row a form adds; the key is the level's own. */
export function buildRow(type: string, key: string, values: AddValues): EditorRow {
	if (type === "DocType") return { key, item_type: "DocType", link_doctype: "DocType", link_to: values.doctype };
	if (type === "Record") return { key, item_type: "Record", link_doctype: values.doctype, link_to: values.name, ...labelOf(values) };
	if (type === "Page") return { key, item_type: "Page", link_doctype: "Page", link_to: values.page, ...labelOf(values) };
	if (type === "Link") return { key, item_type: "Link", url: values.url.trim(), ...labelOf(values) };
	return {
		key,
		item_type: "Section",
		label: values.label.trim(),
		...(values.collapsible ? { collapsible: 1 as const } : {}),
		...(values.collapsible && values.keepClosed ? { keep_closed: 1 as const } : {}),
	};
}

function labelOf(values: AddValues) {
	return values.label.trim() ? { label: values.label.trim() } : {};
}
