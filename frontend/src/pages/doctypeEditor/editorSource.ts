// The DocType editor's load: `frappe.desk.doctype_editor.load.get_doctype_editor`, and the
// pending DocType `/doctype/new` edits before its first save.
import { runMethod } from "@framework/ui/api";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import { NEW_NAME } from "@framework/ui/utils";
import type { LocationQuery } from "vue-router";
import { COPY_OF } from "@/newRecordValues";
import type {
	FormLayoutRow,
	FormLayoutType,
	LayoutTree,
} from "@/recordPage/formLayoutSource/types";
import { NAMEABLE_TYPES, autonameOf, seriesField } from "./namingRules";
import { DEFAULT_PERMISSION } from "./settingsModel";
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
	editable_grid?: 0 | 1;
	allow_bulk_edit?: 0 | 1;
	is_submittable?: 0 | 1;
	autoname?: string;
	naming_rule?: string;
	title_field?: string;
	description?: string;
	fields: RawMetaField[];
	permissions?: Record<string, unknown>[];
	[property: string]: unknown;
}

/** A Customize load's Property Setter, with the value the app ships. */
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
	/** A child table's parents that the user reads. */
	parents?: string[];
	/** The DocType properties this mode's Settings tab sets. */
	settable_properties?: string[];
	/** The site has its own permission rows (Custom DocPerm). */
	site_permissions?: boolean;
	/** Customize: the app's permission rows (DocPerm). */
	app_permissions?: Record<string, unknown>[];
	/** Why this person cannot change permissions here (Customize without System Manager). */
	permissions_refusal?: string | null;
	/** Not yet saved: `/doctype/new` builds it on the client. */
	pending?: boolean;
	/** Customize: the site's changes, and the property changes Customize Form refuses. */
	custom_fields?: CustomFieldRow[];
	property_setters?: PropertySetterRow[];
	locks?: Record<string, Record<string, string>>;
	fieldtype_changes?: Record<string, string[]>;
	/** A new child table made from its parent's Table field: it stays a child table. */
	kind_fixed?: boolean;
}

export interface CustomFieldRow {
	name: string;
	fieldname: string;
	module?: string;
	is_system_generated: 0 | 1;
}

export interface PropertySetterRow {
	field_name: string | null;
	doctype_or_field: string;
	property: string;
	value: string | null;
	/** The value the app ships; `null` on a custom field. */
	app_value: unknown;
	is_system_generated: 0 | 1;
}

/** The address's `?mode=customize` names the server's `Customize`; any other value asks for the default. */
export function modeOf(query: unknown): EditorMode | undefined {
	return query === "customize"
		? "Customize"
		: query === "design"
			? "Design"
			: undefined;
}

/** A route that names the DocType and mode the canvas holds loads nothing: a first save moves `/doctype/new` to its own. */
export function holdsRoute(state: EditorState | null, name: string, mode: EditorMode | undefined): boolean {
	return state?.doctype === name && state.mode === (mode ?? "Design");
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

/** What `routeForNew("DocType", values)` carried: the dialog's first answers and the DocType a duplicate copies. */
export function carriedAnswers(query: LocationQuery): {
	answers: Partial<NewDoctype>;
	copyOf: string | null;
} {
	const text = (key: string) => {
		const given = query[key];
		return String((Array.isArray(given) ? given[0] : given) ?? "");
	};
	const answers: Partial<NewDoctype> = {};
	const name = text(NEW_NAME) || text("name");
	if (name) answers.name = name;
	if (text("module")) answers.module = text("module");
	if (text("naming_rule")) answers.naming_rule = text("naming_rule");
	if (text("custom")) answers.custom = text("custom") === "1";
	return { answers, copyOf: text(COPY_OF) || null };
}

/** The first answers a duplicate gives: its source's module, kind and naming rule, not its name. */
export function copiedAnswers(source: EditorState): Partial<NewDoctype> {
	const { naming_rule } = source.definition;
	return {
		module: source.module,
		custom: Boolean(source.custom),
		...(naming_rule ? { naming_rule } : {}),
	};
}

/**
 * A DocType that exists only in the editor until its first save. It starts with one Data field, or
 * with a copy of the source's fields and Details layout when it duplicates one.
 */
export function pendingDoctype(answers: NewDoctype, source?: EditorState | null): EditorState {
	const field = {
		fieldname: "title",
		label: "Title",
		fieldtype: "Data",
	} as RawMetaField;
	const definition: DoctypeDefinition = source
		? copiedDefinition(answers, source)
		: {
				name: answers.name,
				module: answers.module,
				custom: answers.custom ? 1 : 0,
				naming_rule: answers.naming_rule,
				autoname: autonameOf(answers.naming_rule, field.fieldname),
				fields: [field],
				permissions: [{ ...DEFAULT_PERMISSION }],
			};
	const layout = (source && detailsLayout(source)?.layout) || [
		{
			name: "details",
			sections: [
				{ name: "main", columns: [{ name: "column", fields: ["title"] }] },
			],
		},
	];
	const named = withSeriesField(definition, layout);
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
			Details: [{ name: null, layout: named.layout, omitted: [], source: "fallback" }],
		},
		definition: named.definition,
		pending: true,
	};
}

/** The DocType's insert needs the naming series field, so it goes first in the first column, made if missing. */
function withSeriesField(definition: DoctypeDefinition, layout: LayoutTree) {
	const needed = String(definition.autoname ?? "").startsWith("naming_series:");
	if (!needed || definition.fields.some((field) => field.fieldname === "naming_series")) {
		return { definition, layout };
	}
	const [tab = { name: "details", sections: [] }, ...tabs] = layout;
	const [section = { name: freeSectionName(layout), columns: [] }, ...sections] = tab.sections;
	const [column = { name: "column_1", fields: [] }, ...columns] = section.columns;
	const first = { ...column, fields: ["naming_series", ...column.fields] };
	return {
		definition: { ...definition, fields: [seriesField(definition.name), ...definition.fields] },
		layout: [{ ...tab, sections: [{ ...section, columns: [first, ...columns] }, ...sections] }, ...tabs],
	};
}

/** Section names are unique across a layout's tabs. */
function freeSectionName(layout: LayoutTree): string {
	const taken = new Set(layout.flatMap((tab) => tab.sections.map((section) => section.name)));
	let at = 1;
	while (taken.has(`section_${at}`)) at++;
	return `section_${at}`;
}

// The source's record identity, which `as_dict` sends on the DocType and each row; a copy gets its own.
const IDENTITY = ["name", "parent", "parenttype", "parentfield", "owner", "creation", "modified", "modified_by"];

function withoutIdentity<T extends object>(row: T): T {
	const copy: Record<string, unknown> = { ...(row as Record<string, unknown>) };
	for (const key of IDENTITY) delete copy[key];
	return copy as T;
}

function firstNameable(fields: RawMetaField[]): string {
	return fields.find((field) => NAMEABLE_TYPES.includes(field.fieldtype))?.fieldname ?? "";
}

function copiedDefinition(answers: NewDoctype, source: EditorState): DoctypeDefinition {
	const { definition } = source;
	const fields = definition.fields.map(withoutIdentity);
	const sameRule = definition.naming_rule === answers.naming_rule;
	const autoname = sameRule ? definition.autoname : autonameOf(answers.naming_rule, firstNameable(fields));
	// "By fieldname" with no field a name can come from: the copy names its records at random instead.
	const unnamed = autoname === "field:";
	return {
		...withoutIdentity(definition),
		name: answers.name,
		module: answers.module,
		custom: answers.custom ? 1 : 0,
		naming_rule: unnamed ? "Random" : answers.naming_rule,
		autoname: unnamed ? "hash" : autoname,
		fields,
	};
}
