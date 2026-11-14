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
		{ type: "Link", label: __("Link"), icon: "lucide-link", rail: true },
		{ type: "Section", label: __("Section"), icon: "lucide-heading", rail: false },
	];
	return all.filter((entry) => container !== RAIL || entry.rail);
}

export type AddValues = { doctype: string; url: string; label: string; collapsible: boolean; keepClosed: boolean };

/** What a form needs filled before "Add row"; the refusal is shown under the field. */
export function missing(type: string, values: AddValues): { field: keyof AddValues; message: string } | null {
	if (type === "DocType" && !values.doctype) return { field: "doctype", message: __("Pick a DocType.") };
	if (type === "Link" && !values.url.trim()) return { field: "url", message: __("Write a link.") };
	if (type === "Section" && !values.label.trim()) return { field: "label", message: __("Give the section a label.") };
	return null;
}

/** The row a form adds; the key is the level's own. */
export function buildRow(type: string, key: string, values: AddValues): EditorRow {
	if (type === "DocType") return { key, item_type: "DocType", link_doctype: "DocType", link_to: values.doctype };
	if (type === "Link") return { key, item_type: "Link", url: values.url.trim(), ...(values.label ? { label: values.label } : {}) };
	return {
		key,
		item_type: "Section",
		label: values.label.trim(),
		...(values.collapsible ? { collapsible: 1 as const } : {}),
		...(values.collapsible && values.keepClosed ? { keep_closed: 1 as const } : {}),
	};
}
