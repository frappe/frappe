// The Design editor's working state: what the editor loaded, with the staged edits replayed on a
// copy. Each act applies as `frappe/desk/doctype_editor/design_edits.py` applies it on save.
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import type { LayoutTree } from "@/recordPage/formLayoutSource/types";
import { addChildTable, reorderField } from "./childReplay";
import {
	appValue,
	customFieldname,
	customizeRules,
	refuseLocked,
	refuseStandard,
	type CustomizeRules,
} from "./customizeRules";
import { detailsLayout, type EditorState } from "./editorSource";
import { fieldnameFromLabel, LAYOUT_BREAKS, validFieldname } from "./fieldRules";
import { EditRefused, LayoutTreeEditor } from "./layoutTree";

export { EditRefused } from "./layoutTree";

/** An edit as the save sends it: the act and its keys side by side. */
export interface FlatEdit {
	act: string;
	[key: string]: unknown;
}

export interface WorkingState {
	doctype: string;
	standard: boolean;
	fields: RawMetaField[];
	/** The Details layout the canvas draws. */
	layout: LayoutTree;
	description: string;
	/** The fieldnames the database has; a rename or delete checks against them. */
	saved: string[];
	/** Each saved field renamed so far, `[saved, current]`. */
	renames: [string, string][];
	/** `null` in Design. */
	customize: CustomizeRules | null;
}

export interface OffLayoutField {
	field: RawMetaField;
	/** Added since the last save. */
	new: boolean;
	/** Named by the last save's mandatory error. */
	asked: boolean;
}

export function editorBase(state: EditorState): WorkingState {
	const { definition } = state;
	return {
		doctype: state.doctype,
		standard: !state.custom,
		fields: definition.fields,
		layout: detailsLayout(state)?.layout ?? [],
		description: definition.description ?? "",
		saved: definition.fields.map((field) => field.fieldname),
		renames: [],
		customize: customizeRules(state),
	};
}

/** The base with `edits` applied in order; the base is never changed, so undo is a shorter replay. */
export function workingState(base: WorkingState, edits: readonly FlatEdit[]): WorkingState {
	const replay = new DesignReplay(structuredClone(base), base);
	for (const edit of edits) replay.apply(edit);
	return replay.state;
}

/** The tray's fields: every field the Details layout does not place, layout breaks aside. */
export function fieldsOffLayout(working: WorkingState, askedOnSave: readonly string[] = []): OffLayoutField[] {
	const placed = new Set(new LayoutTreeEditor(working.layout).fieldnames());
	return working.fields
		.filter((field) => !placed.has(field.fieldname) && !LAYOUT_BREAKS.includes(field.fieldtype))
		.map((field) => ({
			field,
			new: savedName(working, field.fieldname) === null,
			asked: askedOnSave.includes(field.fieldname),
		}));
}

/** Mandatory fields a condition can hide, with the tab, section or column that hides them. */
export function reqdInConditional(working: WorkingState): { fieldname: string; container: string }[] {
	const reqd = new Set(working.fields.filter((field) => field.reqd).map((field) => field.fieldname));
	const found: { fieldname: string; container: string }[] = [];
	for (const tab of working.layout) {
		for (const section of tab.sections) {
			for (const column of section.columns) {
				const hider = [tab, section, column].find((container) => container.dependsOn);
				if (!hider) continue;
				for (const entry of column.fields) {
					if (typeof entry === "string" && reqd.has(entry)) {
						found.push({ fieldname: entry, container: hider.name ?? "" });
					}
				}
			}
		}
	}
	return found;
}

const DOCTYPE_PROPERTIES = ["description", "editable_grid", "allow_bulk_edit"];
const RESERVED_PROPERTIES = ["name", "parent", "parenttype", "parentfield", "idx", "doctype"];
const PLACE_KEYS = ["fieldname", "section", "column", "index", "tab"];
const CANVAS_ACTS: Record<string, keyof LayoutTreeEditor> = {
	"canvas.add_tab": "add_tab",
	"canvas.remove_tab": "remove_tab",
	"canvas.move_tab": "move_tab",
	"canvas.add_section": "add_section",
	"canvas.remove_section": "remove_section",
	"canvas.move_section": "move_section",
	"canvas.add_column": "add_column",
	"canvas.remove_column": "remove_column",
	"canvas.move_column": "move_column",
	"canvas.set_container_property": "set_container_property",
	"canvas.place_field": "place_field",
	"canvas.move_field": "place_field",
	"canvas.unplace_field": "unplace_field",
};

/** Applies edits to a state it owns, act by act. */
class DesignReplay {
	private tree: LayoutTreeEditor;

	constructor(
		readonly state: WorkingState,
		private loaded: WorkingState,
	) {
		this.tree = new LayoutTreeEditor(state.layout);
	}

	apply(edit: FlatEdit) {
		const method = CANVAS_ACTS[edit.act];
		if (method) return this.canvas(edit, method);
		const handler = FIELD_ACTS[edit.act];
		if (!handler) throw new EditRefused("{0} is not a Design edit.", [edit.act]);
		handler(this, edit as never);
	}

	canvas(edit: FlatEdit, method: keyof LayoutTreeEditor) {
		if (method === "place_field" || method === "unplace_field") this.field(edit.fieldname as string);
		if (drawsDetails(edit)) (this.tree[method] as (edit: FlatEdit) => void)(edit);
	}

	addField(edit: FlatEdit & { label?: string; fieldtype?: string; fieldname?: string; options?: string }) {
		const { label, fieldtype } = edit;
		if (!label || !fieldtype) throw new EditRefused("A new field needs a label and a type.");
		const fieldname = edit.fieldname || newFieldname(this.state, label);
		this.refuseTakenFieldname(fieldname);
		const properties = (edit.properties ?? {}) as Record<string, unknown>;
		for (const property of Object.keys(properties)) refuseProperty(property);
		const options = edit.options ? { options: edit.options } : {};
		this.state.fields.push({ ...properties, fieldname, label, fieldtype, ...options } as RawMetaField);
		if (edit.layout) this.canvas({ ...pick(edit, PLACE_KEYS), act: edit.act, layout: edit.layout, fieldname }, "place_field");
	}

	/** The read-only field `fields.fetch_field` adds; the edit carries the source's label and type. */
	fetchField(edit: FlatEdit & { link?: string; source?: string }) {
		const link = this.field(edit.link as string);
		if (link.fieldtype !== "Link" || !link.options) throw new EditRefused("{0} is not a Link field.", [link.fieldname]);
		this.addField({ ...edit, properties: { fetch_from: `${link.fieldname}.${edit.source}`, read_only: 1 } });
	}

	setFieldProperty({ fieldname, property, value }: { fieldname: string; property: string; value: unknown }) {
		const field = this.field(fieldname);
		refuseProperty(property);
		if (this.state.customize) refuseLocked(this.state.customize, field, property);
		(field as unknown as Record<string, unknown>)[property] = value;
	}

	resetFieldProperty({ fieldname, property }: { fieldname: string; property: string }) {
		const rules = this.state.customize;
		if (!rules) throw new EditRefused("{0} is not a Design edit.", ["fields.reset_field_property"]);
		const field = this.field(fieldname);
		refuseProperty(property);
		const loaded = this.loaded.fields.find((each) => each.fieldname === fieldname);
		if (!loaded || !rules.standard.includes(fieldname)) {
			throw new EditRefused("Only a standard field's property can be reset.");
		}
		(field as unknown as Record<string, unknown>)[property] = appValue(rules, loaded, property);
	}

	renameField({ fieldname, new_fieldname }: { fieldname: string; new_fieldname?: string }) {
		const field = this.field(fieldname);
		if (this.state.customize) {
			refuseStandard(this.state.customize, fieldname, "Only a custom field this site added can be renamed.");
			if (!new_fieldname?.startsWith("custom_")) {
				throw new EditRefused("A custom field's fieldname starts with custom_.");
			}
		}
		if (!new_fieldname) throw new EditRefused("A field needs a fieldname.");
		const saved = savedName(this.state, fieldname);
		if (new_fieldname !== saved) this.refuseTakenFieldname(new_fieldname);
		if (saved !== null) {
			if (this.state.standard && !this.state.customize) {
				throw new EditRefused("Renaming a saved field of a standard DocType needs a patch.");
			}
			this.noteRename(saved, new_fieldname);
		}
		field.fieldname = new_fieldname;
		this.tree.rename_field(fieldname, new_fieldname);
	}

	deleteField({ fieldname }: { fieldname: string }) {
		const field = this.field(fieldname);
		if (this.state.customize) {
			refuseStandard(this.state.customize, fieldname, "{0} is a standard field. Hide it instead.");
		}
		this.state.fields.splice(this.state.fields.indexOf(field), 1);
		this.state.renames = this.state.renames.filter(([, current]) => current !== fieldname);
		this.tree.unplace_field({ fieldname });
	}

	setDoctypeProperty({ property, value }: { property: string; value: unknown }) {
		if (!DOCTYPE_PROPERTIES.includes(property)) throw new EditRefused("{0} is not a DocType setting.", [property]);
		if (property === "description") this.state.description = (value as string) ?? "";
	}

	private field(fieldname: string): RawMetaField {
		const field = this.state.fields.find((each) => each.fieldname === fieldname);
		if (!field) throw new EditRefused("{0} is not a field of {1}.", [fieldname, this.state.doctype]);
		return field;
	}

	/** A deleted field keeps its column, so the server also refuses its name; only the save knows that. */
	private refuseTakenFieldname(fieldname: string) {
		if (!validFieldname(fieldname)) {
			throw new EditRefused(
				"{0} is not a valid fieldname. Use lowercase letters, digits and underscores.",
				[fieldname],
			);
		}
		if (this.state.fields.some((field) => field.fieldname === fieldname)) {
			throw new EditRefused("{0} already has a field {1}.", [this.state.doctype, fieldname]);
		}
	}

	/** Folds a chain of renames, so the data moves once from the saved column. */
	private noteRename(saved: string, renamed: string) {
		this.state.renames = this.state.renames.filter(([from]) => from !== saved);
		if (renamed !== saved) this.state.renames.push([saved, renamed]);
	}
}

const FIELD_ACTS: Record<string, (replay: DesignReplay, edit: never) => void> = {
	"fields.add_field": (replay, edit) => replay.addField(edit),
	"fields.fetch_field": (replay, edit) => replay.fetchField(edit),
	"fields.set_field_property": (replay, edit) => replay.setFieldProperty(edit),
	"fields.reset_field_property": (replay, edit) => replay.resetFieldProperty(edit),
	"fields.rename_field": (replay, edit) => replay.renameField(edit),
	"fields.delete_field": (replay, edit) => replay.deleteField(edit),
	"fields.reorder_field": (replay, edit) => reorderField(replay.state, edit),
	"fields.add_child_table": (replay, edit) => addChildTable(replay.state, edit, (added) => replay.addField(added)),
	"settings.set_doctype_property": (replay, edit) => replay.setDoctypeProperty(edit),
};

/** The fieldname the database has for this field; `null` for a field added since the save. */
export function savedName(state: WorkingState, fieldname: string): string | null {
	const renamed = state.renames.find(([, current]) => current === fieldname);
	if (renamed) return renamed[0];
	return state.saved.includes(fieldname) ? fieldname : null;
}

/** A new field's fieldname: in Customize, a custom field's `custom_` one. */
export function newFieldname(state: WorkingState, label: string): string {
	return state.customize ? customFieldname(label) : fieldnameFromLabel(label);
}

/** The canvas draws the default Details layout; edits to other layouts leave it as it is. */
function drawsDetails(edit: FlatEdit): boolean {
	const layout = edit.layout as { type?: string; id?: string } | undefined;
	return layout?.type === "Details" && !layout.id;
}

function refuseProperty(property: string) {
	if (property === "fieldname") throw new EditRefused("Rename the field to change its fieldname.");
	if (RESERVED_PROPERTIES.includes(property)) throw new EditRefused("{0} is not a field property.", [property]);
}

function pick(edit: FlatEdit, keys: string[]): Record<string, unknown> {
	return Object.fromEntries(keys.filter((key) => key in edit).map((key) => [key, edit[key]]));
}
