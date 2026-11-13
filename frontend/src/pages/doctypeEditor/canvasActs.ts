// The Details canvas's acts. Drag, Alt+Arrow, the menus and the palette all run these, so each
// change stages through one path; an act's value is the keys of the edit it stages.
import type { ActItem } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import { DETAILS, type CanvasSelection, type DesignCanvas } from "./designCanvas";
import { newFieldname, type FlatEdit } from "./editorModel";
import { validFieldname } from "./fieldRules";
import type { EditorActsHost } from "./editorActs";
import { fetchedFieldname, type FetchSource } from "./fetchFrom";

type Keys = Record<string, unknown>;

export function canvasItems(host: EditorActsHost): ActItem<EditorActsHost>[] {
	const when = () => editing(host);
	const staging: [name: string, label: string][] = [
		["remove_tab", __("Remove tab")],
		["move_tab", __("Move tab")],
		["remove_section", __("Remove section")],
		["move_section", __("Move section")],
		["add_column", __("Add column")],
		["remove_column", __("Remove column")],
		["move_column", __("Move column")],
		["place_field", __("Place field")],
		["move_field", __("Move field")],
		["unplace_field", __("Remove from layout")],
		["set_container_property", __("Set a container property")],
	];
	const staged = staging.map(([name, label]) => ({
		name,
		label,
		palette: false as const,
		when,
		run: (_context: EditorActsHost, keys: Keys) => stage(host, `canvas.${name}`, keys),
	}));
	return [
		{
			name: "add_tab",
			label: __("Add tab"),
			icon: "plus",
			when,
			run: (_context, keys?: Keys) => {
				const canvas = host.canvas()!;
				const added = adds(canvas, () => stage(host, "canvas.add_tab", keys ?? {}), tabNames);
				if (added) canvas.select({ kind: "tab", tab: added });
			},
		},
		{
			name: "add_section",
			label: __("Add section"),
			icon: "plus",
			when,
			run: (_context, keys?: Keys) => {
				const canvas = host.canvas()!;
				const into = keys ?? { tab: canvas.openTab.value?.name };
				const added = adds(canvas, () => stage(host, "canvas.add_section", into), sectionNames);
				if (added) canvas.select({ kind: "section", section: added });
			},
		},
		...staged,
		{
			name: "select",
			label: __("Select"),
			palette: false,
			when: () => Boolean(host.canvas()),
			run: (_context, selection: CanvasSelection | null) => host.canvas()!.select(selection),
		},
	];
}

/** One property, or several staged as one undo step, as a type change sets type and options. */
type PropertyKeys = { fieldname: string } & (
	| { property: string; value: unknown }
	| { properties: Record<string, unknown> }
);

/** The `fields` acts of the canvas and the field panel. */
export function fieldItems(host: EditorActsHost): ActItem<EditorActsHost>[] {
	const when = () => editing(host);
	return [
		{
			name: "add_field",
			label: __("Add field"),
			icon: "plus",
			key: "A",
			when: () => editing(host),
			run: (_context, keys?: Keys & { label: string; fieldname?: string }) => {
				const canvas = host.canvas()!;
				if (!keys) return void (canvas.adding.value = canvas.targetSection());
				canvas.stage(placedOn(DETAILS, { ...keys, act: "fields.add_field" }));
				canvas.select({ kind: "field", fieldname: keys.fieldname || newFieldname(canvas.working.value, keys.label) });
			},
		},
		{
			name: "set_field_property",
			label: __("Set a field property"),
			palette: false,
			when,
			run: (_context, keys: PropertyKeys) => setFieldProperties(host.canvas()!, keys),
		},
		{
			name: "fetch_field",
			label: __("Fetch a field"),
			palette: false,
			when,
			run: (_context, keys: { link: string; source: FetchSource }) => fetchField(host.canvas()!, keys),
		},
		{
			name: "reset_field_property",
			label: __("Reset a field property"),
			palette: false,
			when: () => editing(host) && Boolean(host.canvas()?.customize),
			run: (_context, keys: { fieldname: string; property: string }) =>
				host.canvas()!.stage({ ...keys, act: "fields.reset_field_property" }),
		},
		{
			name: "rename_field",
			label: __("Rename field"),
			palette: false,
			when,
			run: (_context, keys: { fieldname: string; new_fieldname: string }) => {
				const canvas = host.canvas()!;
				canvas.stage({ ...keys, act: "fields.rename_field" });
				reselect(canvas, keys.fieldname, keys.new_fieldname);
			},
		},
		{
			name: "delete_field",
			label: __("Remove field"),
			palette: false,
			when,
			run: (_context, keys: { fieldname: string }) => {
				const canvas = host.canvas()!;
				canvas.stage({ ...keys, act: "fields.delete_field" });
				const selected = canvas.selection.value;
				if (selected?.kind === "field" && selected.fieldname === keys.fieldname) canvas.select(null);
			},
		},
	];
}

/** A field edit that names a place puts the field on `layout`. */
function placedOn(layout: { type: string; id?: string }, edit: FlatEdit): FlatEdit {
	return "section" in edit || "tab" in edit ? { ...edit, layout } : edit;
}

/** A read-only field filled from the Link's record, right after the Link, then selected. */
function fetchField(canvas: DesignCanvas, { link, source }: { link: string; source: FetchSource }) {
	const fieldname = fetchedFieldname(source, canvas.working.value.fields.map((field) => field.fieldname));
	const place = canvas.place(link);
	const at = place ? { section: place.section, column: place.column, index: place.index + 1 } : {};
	const options = source.options ? { options: source.options } : {};
	const label = source.label || source.fieldname;
	const typed = { fieldname, label, fieldtype: source.fieldtype, ...options };
	canvas.stage(placedOn(DETAILS, { act: "fields.fetch_field", link, source: source.fieldname, ...typed, ...at }));
	canvas.select({ kind: "field", fieldname });
}

/** A label edit of a field added since the save renames it too, in the same undo step. */
function setFieldProperties(canvas: DesignCanvas, keys: PropertyKeys) {
	const { fieldname } = keys;
	const properties = "properties" in keys ? keys.properties : { [keys.property]: keys.value };
	const edits: FlatEdit[] = Object.entries(properties).map(([property, value]) => ({
		act: "fields.set_field_property",
		fieldname,
		property,
		value,
	}));
	const follows = "label" in properties ? followedName(canvas, fieldname, String(properties.label ?? "")) : null;
	if (follows) edits.push({ act: "fields.rename_field", fieldname, new_fieldname: follows });
	canvas.stage(...edits);
	if (follows) reselect(canvas, fieldname, follows);
}

/** The fieldname a new field's label spells, unless it is the same, invalid or another field's. */
function followedName(canvas: DesignCanvas, fieldname: string, label: string): string | null {
	if (canvas.savedName(fieldname)) return null;
	const next = newFieldname(canvas.working.value, label);
	if (next === fieldname || !validFieldname(next) || canvas.field(next)) return null;
	return next;
}

function reselect(canvas: DesignCanvas, from: string, to: string) {
	const selected = canvas.selection.value;
	if (selected?.kind === "field" && selected.fieldname === from) canvas.select({ kind: "field", fieldname: to });
}

function editing(host: EditorActsHost) {
	return host.tab.value === "editor" && Boolean(host.canvas()?.editable);
}

function stage(host: EditorActsHost, act: string, keys: Keys) {
	host.canvas()!.stage({ ...keys, act, layout: DETAILS });
}

/** The name the staging added, found by the names before and after. */
function adds(canvas: DesignCanvas, staging: () => void, names: (canvas: DesignCanvas) => string[]) {
	const before = new Set(names(canvas));
	staging();
	return names(canvas).find((name) => !before.has(name));
}

function tabNames(canvas: DesignCanvas) {
	return canvas.tabs.value.map((tab) => tab.name!);
}

function sectionNames(canvas: DesignCanvas) {
	return canvas.tabs.value.flatMap((tab) => tab.sections.map((section) => section.name!));
}
