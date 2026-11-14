// The child-table acts on a working state, as `design_edits.py` applies them on save.
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import type { FlatEdit, WorkingState } from "./editorModel";
import { TABLE_TYPES } from "./fieldtypes";
import { EditRefused } from "./layoutTree";

/** Moves a field to `index` in the field order, which is also the grid's column order. */
export function reorderField(state: WorkingState, { fieldname, index }: { fieldname: string; index?: number }) {
	const field = fieldOf(state, fieldname);
	state.fields.splice(state.fields.indexOf(field), 1);
	state.fields.splice(index ?? state.fields.length, 0, field);
}

/** Points the table field at the new child, adding the field when the edit names none yet.
 * A child of `link` is a Table MultiSelect's. */
export function addChildTable(
	state: WorkingState,
	edit: { name?: string; table_field?: string; label?: string; link?: string },
	addField: (edit: FlatEdit) => void,
) {
	const { name, table_field } = edit;
	if (!name || !table_field) throw new EditRefused("A new child table needs a name and a table field.");
	const table = state.fields.find((field) => field.fieldname === table_field);
	if (!table) {
		return addField({ ...edit, act: "fields.add_field", fieldname: table_field, label: edit.label || name, fieldtype: edit.link ? "Table MultiSelect" : "Table", options: name });
	}
	if (!TABLE_TYPES.includes(table.fieldtype)) throw new EditRefused("{0} is not a Table field.", [table_field]);
	table.options = name;
}

function fieldOf(state: WorkingState, fieldname: string): RawMetaField {
	const field = state.fields.find((each) => each.fieldname === fieldname);
	if (!field) throw new EditRefused("{0} is not a field of {1}.", [fieldname, state.doctype]);
	return field;
}
