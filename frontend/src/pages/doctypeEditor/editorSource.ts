// The DocType editor's load: `frappe.desk.doctype_editor.load.get_doctype_editor`, and the
// pending DocType `/doctype/new` edits before its first save.
import { runMethod } from "@framework/ui/api";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import type {
	FormLayoutRow,
	FormLayoutType,
} from "@/recordPage/formLayoutSource/types";
import type { BaseVersion, EditorMode } from "./pendingEdits";

export type LayoutSource =
	"site" | "app" | "fallback" | "none" | "same as Details";

export interface EditorLayout extends FormLayoutRow {
	source: LayoutSource;
	app?: string | null;
}

export interface DoctypeDefinition {
	name: string;
	module?: string;
	custom?: 0 | 1;
	istable?: 0 | 1;
	issingle?: 0 | 1;
	autoname?: string;
	naming_rule?: string;
	title_field?: string;
	fields: RawMetaField[];
}

export interface EditorState {
	doctype: string;
	mode: EditorMode;
	modes: EditorMode[];
	base_version: BaseVersion;
	custom: 0 | 1;
	module: string;
	app_title: string | null;
	record_count: number | null;
	value_counts: Record<string, number>;
	layouts: Partial<Record<FormLayoutType, EditorLayout[]>>;
	/** Design: the DocType as its app ships it. Customize sends the site meta's fields instead. */
	definition: DoctypeDefinition;
	site_custom_fields?: number;
	/** Not yet saved: `/doctype/new` builds it on the client. */
	pending?: boolean;
}

/** The address's `?mode=customize` names the server's `Customize`; any other value asks for the default. */
export function modeOf(query: unknown): EditorMode | undefined {
	return query === "customize"
		? "Customize"
		: query === "design"
			? "Design"
			: undefined;
}

export async function loadEditor(
	doctype: string,
	mode?: EditorMode,
): Promise<EditorState> {
	const { data } = await runMethod<EditorState>(
		"frappe.desk.doctype_editor.load.get_doctype_editor",
		mode ? { doctype, mode } : { doctype },
		{ http: "GET" },
	);
	return data;
}

/** The Details layout the canvas draws: the default row, which Design on an app's DocType takes from the app. */
export function detailsLayout(state: EditorState): EditorLayout | null {
	const rows = state.layouts.Details ?? [];
	const own =
		state.mode === "Design" && !state.custom
			? rows.filter((row) => row.source !== "site")
			: rows;
	return own.find((row) => !row.condition) ?? own[0] ?? rows[0] ?? null;
}

export interface NewDoctype {
	name: string;
	module: string;
	custom: boolean;
	naming_rule: string;
}

/** A DocType that exists only in the editor until its first save; it starts with one Data field. */
export function pendingDoctype(answers: NewDoctype): EditorState {
	const field = {
		fieldname: "title",
		label: "Title",
		fieldtype: "Data",
	} as RawMetaField;
	const layout = [
		{
			name: "details",
			sections: [
				{ name: "main", columns: [{ name: "column", fields: ["title"] }] },
			],
		},
	];
	return {
		doctype: answers.name,
		mode: "Design",
		modes: ["Design"],
		base_version: { doctype: "", layouts: {}, app_layouts: {} },
		custom: answers.custom ? 1 : 0,
		module: answers.module,
		app_title: null,
		record_count: null,
		value_counts: {},
		layouts: {
			Details: [{ name: null, layout, omitted: [], source: "fallback" }],
		},
		definition: {
			name: answers.name,
			module: answers.module,
			naming_rule: answers.naming_rule,
			fields: [field],
		},
		pending: true,
	};
}
