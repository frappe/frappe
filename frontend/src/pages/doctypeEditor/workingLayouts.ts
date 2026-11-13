// Every layout of the DocType in the editor's working state, as `design_state.py` and
// `customize_state.py` hold them on save: what each type has, and the default its fallback makes.
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import type { FormLayoutType, LayoutTree } from "@/recordPage/formLayoutSource/types";
import type { DoctypeDefinition, EditorLayout, EditorState, LayoutSource } from "./editorSource";
import { LAYOUT_BREAKS } from "./fieldRules";
import { EditRefused } from "./layoutTree";
import type { EditorMode } from "./pendingEdits";

export const LAYOUT_TYPES: FormLayoutType[] = ["Details", "Side Panel", "Quick Entry", "New Record"];

/** What an edit names: no `id` is the type's default, the one with no condition. */
export interface LayoutRef {
	type: FormLayoutType;
	id?: string;
}

export interface WorkingLayout {
	/** `app:<index>` for an app entry, the row name for a site row; none for a default made from the fallback. */
	id?: string;
	title: string | null;
	condition: string | null;
	source: LayoutSource;
	tabs: LayoutTree;
	omitted: string[];
	/** A site row whose app layout or fallback changed since it was copied. */
	sourceChanged?: boolean;
}

export interface TypeLayouts {
	layouts: WorkingLayout[];
	/** The load's empty entry, which stands in for a missing default. */
	empty: { source: LayoutSource; tabs: LayoutTree } | null;
	/** The app's entries, which Customize's reset goes back to. */
	app: WorkingLayout[];
	/** Customize saves a touched type as site rows. */
	touched: boolean;
}

/** The DocField keys the fallbacks read that the form's field type leaves out. */
type DocField = RawMetaField & { allow_in_quick_entry?: 0 | 1; is_custom_field?: 0 | 1; is_system_generated?: 0 | 1 };

export type WorkingLayouts = Partial<Record<FormLayoutType, TypeLayouts>>;

/** What `layoutOf` and the replay read besides the layouts. */
export interface LayoutsHolder {
	doctype: string;
	mode: EditorMode;
	standard: boolean;
	definition: Pick<DoctypeDefinition, "istable" | "issingle">;
	fields: RawMetaField[];
	saved: string[];
	layouts: WorkingLayouts;
}

/** `layout_type_refusal` in `form_layout.py`: a child table has Details only, a Single no create layouts. */
export function allowedTypes(definition: Pick<DoctypeDefinition, "istable" | "issingle">): FormLayoutType[] {
	if (definition.istable) return ["Details"];
	if (definition.issingle) return ["Details", "Side Panel"];
	return LAYOUT_TYPES;
}

export function loadedLayouts(state: EditorState, standard: boolean): WorkingLayouts {
	const types = allowedTypes(state.definition).map((type) => [type, typeLayouts(state, standard, type)]);
	return Object.fromEntries(types);
}

/** The layout a ref names, or the stand-in for a missing default; `null` for an id that is gone. */
export function layoutOf(working: LayoutsHolder, ref: LayoutRef): WorkingLayout | null {
	const found = findLayout(working, ref);
	if (found || ref.id) return found;
	if (!working.layouts[ref.type]) return null;
	const empty = working.layouts[ref.type]!.empty;
	const source = empty?.source ?? emptySource(ref.type);
	return { title: null, condition: null, source, tabs: fallbackTabs(working, ref.type), omitted: [] };
}

/** The tree a layout draws; empty for one that is gone. */
export function tabsOf(working: LayoutsHolder, ref: LayoutRef): LayoutTree {
	return layoutOf(working, ref)?.tabs ?? [];
}

/** What a type has beneath any site layout: the app's layouts, else what its fallback draws. */
export function baseSource(working: LayoutsHolder, type: FormLayoutType): LayoutSource {
	const of = working.layouts[type];
	if (of?.app.length) return "app";
	return of?.empty?.source ?? emptySource(type);
}

/** `CustomizeState.forked`: the type has a site row, saved or made by an edit. */
export function forked(working: LayoutsHolder, type: FormLayoutType): boolean {
	const of = working.layouts[type];
	return Boolean(of && (of.touched || of.layouts.some((layout) => layout.source === "site")));
}

export function findLayout(working: LayoutsHolder, { type, id }: LayoutRef): WorkingLayout | null {
	const layouts = working.layouts[type]?.layouts ?? [];
	return layouts.find((layout) => (id ? layout.id === id : !layout.condition)) ?? null;
}

/** Where `ref` is after a reload: a save renames rows, so a gone or reused id is found by condition and title. */
export function reloadedRef(working: LayoutsHolder, ref: LayoutRef, was: WorkingLayout | null): LayoutRef {
	if (!ref.id || !was) return ref;
	const same = (layout: WorkingLayout) => (layout.condition ?? "") === (was.condition ?? "");
	const found = findLayout(working, ref);
	if (found && same(found)) return ref;
	const matches = (working.layouts[ref.type]?.layouts ?? []).filter(same);
	const match = matches.find((layout) => (layout.title ?? "") === (was.title ?? "")) ?? matches[0];
	if (!match) return ref;
	return match.condition ? { type: ref.type, id: match.id } : { type: ref.type };
}

/** `fallback_tabs`: what a type with no layout of its own makes its first default from. */
export function fallbackTabs(working: LayoutsHolder, type: FormLayoutType): LayoutTree {
	if (type === "New Record") return structuredClone(tabsOf(working, { type: "Details" }));
	if (type === "Quick Entry") return quickEntryLayout(fallbackFields(working));
	if (type === "Side Panel") return sidePanelTabs();
	return structuredClone(working.layouts.Details?.empty?.tabs ?? []);
}

/** `side_panel_tabs`: the record panel draws a section's header, and its open state, only from a label. */
export function sidePanelTabs(): LayoutTree {
	const tabs = emptyTabs();
	tabs[0].sections[0].label = "Details";
	return tabs;
}

export function emptyTabs(): LayoutTree {
	return [{ name: "first_tab", sections: [{ name: "section_1", columns: [{ name: "column_1", fields: [] }] }] }];
}

export function typeRefusal(working: LayoutsHolder, type: FormLayoutType): EditRefused | null {
	if (!LAYOUT_TYPES.includes(type)) return new EditRefused("{0} is not a layout type.", [String(type)]);
	if (allowedTypes(working.definition).includes(type)) return null;
	if (working.definition.istable) {
		return new EditRefused("{0} is a child table, so it has only a Details layout.", [working.doctype]);
	}
	return new EditRefused("{0} is a Single, which is never created, so it has no {1} layout.", [working.doctype, type]);
}

function typeLayouts(state: EditorState, standard: boolean, type: FormLayoutType): TypeLayouts {
	const rows = state.layouts[type] ?? [];
	const site = rows.filter((row) => row.source === "site" && !row.app);
	const app = rows.filter((row) => row.source === "app");
	const own = state.mode === "Customize" ? (site.length ? site : app) : standard ? app : site;
	const empty = rows.find((row) => !["site", "app"].includes(row.source));
	return {
		layouts: own.map((row) => working(row, app.indexOf(row))),
		empty: empty ? { source: empty.source, tabs: empty.layout ?? [] } : null,
		app: app.map((row, index) => working(row, index)),
		touched: false,
	};
}

function working(row: EditorLayout, appIndex: number): WorkingLayout {
	return {
		id: row.source === "app" ? `app:${appIndex}` : String(row.name),
		title: row.title ?? null,
		condition: row.condition ?? null,
		source: row.source,
		tabs: structuredClone(row.layout),
		omitted: row.omitted ?? [],
		...(row.source_changed ? { sourceChanged: true } : {}),
	};
}

function emptySource(type: FormLayoutType): LayoutSource {
	if (type === "Details") return "fallback";
	return type === "New Record" ? "same as Details" : "none";
}

/** Customize's fork leaves the site's custom fields out: they keep rendering at their anchors. */
function fallbackFields(working: LayoutsHolder): DocField[] {
	const fields: DocField[] = working.fields;
	if (working.mode !== "Customize") return fields;
	return fields.filter(
		(field) => working.saved.includes(field.fieldname) && !(field.is_custom_field && !field.is_system_generated),
	);
}

/** `quick_entry_layout` in `form_layout.py`: the fields Create asks for, a section per condition. */
function quickEntryLayout(fields: DocField[]): LayoutTree {
	const sections: LayoutTree[number]["sections"] = [];
	for (const field of fields.filter(inQuickEntry)) {
		const condition = field.reqd || field.allow_in_quick_entry ? null : field.mandatory_depends_on;
		if (condition || !sections.length || sections.at(-1)!.dependsOn) {
			sections.push({
				name: `section_${sections.length + 1}`,
				hideBorder: true,
				...(condition ? { dependsOn: condition } : {}),
				columns: [{ name: "column_1", fields: [] }],
			});
		}
		sections.at(-1)!.columns[0].fields.push(field.fieldname);
	}
	return sections.length ? [{ name: "first_tab", sections }] : emptyTabs();
}

function inQuickEntry(field: DocField): boolean {
	const asked = field.reqd || field.allow_in_quick_entry || field.mandatory_depends_on;
	return Boolean(asked) && !field.read_only && !field.is_virtual && !LAYOUT_BREAKS.includes(field.fieldtype);
}
