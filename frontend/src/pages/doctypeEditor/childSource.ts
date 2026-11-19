// A child table made from the parent's editor: its prefilled name, and the pending DocType its
// editor opens until the parent's save inserts it.
import type { EditorState } from "./editorSource";
import { fieldnameFromLabel } from "./fieldRules";

/** "<Parent> <singular label>", so "Sales Invoice" and "Payment Plans" make "Sales Invoice Payment Plan". */
export function newChildName(parent: string, label: string): string {
	const words = label.trim().split(/\s+/).filter(Boolean);
	if (!words.length) return `${parent} Item`;
	words.push(singular(words.pop()!));
	return [parent, ...words].join(" ");
}

// The server suffixes a Link fieldname that is a row column (`doctype`, `parent`, …) the same way.
const ROW_COLUMNS = ["doctype", "name", "owner", "creation", "modified", "modified_by", "docstatus", "idx", "parent", "parentfield", "parenttype"];

function linkFieldname(link: string): string {
	const fieldname = fieldnameFromLabel(link);
	return ROW_COLUMNS.includes(fieldname) ? `${fieldname}_link` : fieldname;
}

/** An empty child table in the parent's module, custom when the parent is.
 * A child of `link` holds that one Link field. */
export function pendingChild(name: string, parent: EditorState, link?: string): EditorState {
	const fields = link ? [{ fieldname: linkFieldname(link), label: link, fieldtype: "Link", options: link, in_list_view: 1 as const }] : [];
	return {
		doctype: name,
		mode: "Design",
		modes: ["Design"],
		base_version: { doctype: "", layouts: {}, app_layouts: {} },
		custom: parent.custom,
		module: parent.module,
		app_title: null,
		record_count: null,
		value_counts: {},
		layouts: {
			Details: [{ name: null, layout: [{ name: "details", sections: [{ name: "main", columns: [{ name: "column", fields: [] }] }] }], omitted: [], source: "fallback" }],
		},
		definition: { name, module: parent.module, custom: parent.custom, istable: 1, editable_grid: 1, allow_bulk_edit: 1, fields },
		parents: [],
		pending: true,
		kind_fixed: true,
	};
}

function singular(word: string): string {
	if (/ies$/i.test(word)) return word.slice(0, -3) + "y";
	if (/(ss|us|is)$/i.test(word)) return word;
	if (/sses$/i.test(word)) return word.slice(0, -2);
	return word.replace(/s$/i, "");
}
